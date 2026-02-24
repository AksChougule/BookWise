from __future__ import annotations

from datetime import datetime, timezone
import logging
import time
from typing import Any, Literal

from pydantic import ValidationError
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.clients.openai_llm import (
    OpenAILLMClient,
    OpenAILLMClientOutputError,
    OpenAILLMClientTransportError,
)
from app.clients.openlibrary import OpenLibraryClient
from app.core.config import get_app_config
from app.db import session as db_session
from app.db.models import BookGeneration
from app.llm.prompts import PROMPT_VERSION, SCHEMA_VERSION, build_prompt
from app.observability.metrics import increment, observe_ms
from app.schemas.generation import ChaptersOut, CritiqueOut, KeyIdeasOut, OverviewOut
from app.services.book_service import (
    BookResolveNotFoundError,
    BookResolveUpstreamError,
    get_book_by_work_id,
    resolve_and_upsert_from_openlibrary,
)

logger = logging.getLogger(__name__)

SectionName = Literal["overview", "key_ideas", "chapters", "critique"]
SCHEMA_VERSION_VALUE = SCHEMA_VERSION
RETRY_AFTER_MS = 500


class GenerationNotFoundError(Exception):
    pass


class GenerationInvalidSectionError(Exception):
    pass


class GenerationOutputValidationError(Exception):
    pass


class GenerationUpstreamError(Exception):
    pass


class GenerationInProgressError(Exception):
    def __init__(self, retry_after_ms: int = RETRY_AFTER_MS) -> None:
        self.retry_after_ms = retry_after_ms
        super().__init__("Generation in progress")


class GenerationPreviouslyFailedError(Exception):
    def __init__(self, error_code: str | None) -> None:
        self.error_code = error_code
        super().__init__("Generation previously failed")


_SECTION_MODEL_MAP = {
    "overview": OverviewOut,
    "key_ideas": KeyIdeasOut,
    "chapters": ChaptersOut,
    "critique": CritiqueOut,
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _get_json_schema(section: SectionName) -> dict[str, Any]:
    schema_model = _SECTION_MODEL_MAP[section]
    return schema_model.model_json_schema()


def _validate_section(section: str) -> SectionName:
    if section not in _SECTION_MODEL_MAP:
        raise GenerationInvalidSectionError("Invalid section")
    return section  # type: ignore[return-value]


def _build_book_context(book_authors: str, title: str, first_publish_year: int | None) -> dict[str, Any]:
    return {
        "title": title,
        "authors": book_authors,
        "first_publish_year": first_publish_year,
        "description": None,
        "subjects": [],
    }


def _parse_and_validate_content(section: SectionName, content: dict[str, Any]) -> dict[str, Any]:
    model = _SECTION_MODEL_MAP[section]
    parsed = model.model_validate(content)
    return parsed.model_dump()


def _find_generation(
    session: Session,
    *,
    book_id: str,
    section: str,
    prompt_version: str,
    provider: str,
    model: str,
) -> BookGeneration | None:
    statement = select(BookGeneration).where(
        BookGeneration.book_id == book_id,
        BookGeneration.section == section,
        BookGeneration.prompt_version == prompt_version,
        BookGeneration.provider == provider,
        BookGeneration.model == model,
    )
    return session.exec(statement).first()


def _handle_existing_non_force(existing: BookGeneration) -> BookGeneration:
    if existing.status == "complete":
        return existing
    if existing.status == "pending":
        raise GenerationInProgressError()
    raise GenerationPreviouslyFailedError(existing.error_code)


def _transition_existing_to_pending(session: Session, generation_id: int) -> bool:
    now = _utc_now()
    db_started = time.perf_counter()
    stmt = (
        update(BookGeneration)
        .where(
            BookGeneration.id == generation_id,
            BookGeneration.status.in_(["failed", "complete"]),
        )
        .values(
            status="pending",
            started_at=now,
            finished_at=None,
            error_code=None,
            error_message=None,
            content_json=None,
            attempt_count=BookGeneration.attempt_count + 1,
            updated_at=now,
        )
    )
    result = session.exec(stmt)
    session.commit()
    observe_ms("db.upsert_ms", (time.perf_counter() - db_started) * 1000.0, labels={"status": "pending"})
    return result.rowcount == 1


def _claim_or_observe_generation(
    session: Session,
    *,
    book_id: str,
    section: SectionName,
    prompt_version: str,
    provider: str,
    model: str,
    schema_version: str,
    force: bool,
) -> tuple[str, BookGeneration]:
    existing = _find_generation(
        session,
        book_id=book_id,
        section=section,
        prompt_version=prompt_version,
        provider=provider,
        model=model,
    )

    if existing is not None and not force:
        observed = _handle_existing_non_force(existing)
        return "observed_complete", observed

    if existing is not None and force:
        if existing.status == "pending":
            raise GenerationInProgressError()
        claimed = _transition_existing_to_pending(session, existing.id)
        if claimed:
            refreshed = session.get(BookGeneration, existing.id)
            if refreshed is None:
                raise GenerationUpstreamError("Failed to claim generation")
            return "claimed", refreshed

        latest = _find_generation(
            session,
            book_id=book_id,
            section=section,
            prompt_version=prompt_version,
            provider=provider,
            model=model,
        )
        if latest is None:
            raise GenerationUpstreamError("Generation row unavailable")
        if latest.status == "pending":
            raise GenerationInProgressError()
        if latest.status == "complete":
            return "observed_complete", latest
        raise GenerationPreviouslyFailedError(latest.error_code)

    pending_row = BookGeneration(
        book_id=book_id,
        section=section,
        status="pending",
        provider=provider,
        model=model,
        prompt_version=prompt_version,
        schema_version=schema_version,
        started_at=_utc_now(),
        attempt_count=1,
    )
    session.add(pending_row)
    db_started = time.perf_counter()
    try:
        session.commit()
        session.refresh(pending_row)
        observe_ms(
            "db.upsert_ms",
            (time.perf_counter() - db_started) * 1000.0,
            labels={"section": section, "status": "pending"},
        )
        return "claimed", pending_row
    except IntegrityError:
        session.rollback()

    latest = _find_generation(
        session,
        book_id=book_id,
        section=section,
        prompt_version=prompt_version,
        provider=provider,
        model=model,
    )
    if latest is None:
        raise GenerationUpstreamError("Unable to resolve generation state")

    if not force:
        observed = _handle_existing_non_force(latest)
        return "observed_complete", observed

    if latest.status == "pending":
        raise GenerationInProgressError()

    claimed = _transition_existing_to_pending(session, latest.id)
    if claimed:
        refreshed = session.get(BookGeneration, latest.id)
        if refreshed is None:
            raise GenerationUpstreamError("Failed to claim generation")
        return "claimed", refreshed

    latest_after = session.get(BookGeneration, latest.id)
    if latest_after is None:
        raise GenerationUpstreamError("Generation row unavailable")
    if latest_after.status == "pending":
        raise GenerationInProgressError()
    if latest_after.status == "complete":
        return "observed_complete", latest_after
    raise GenerationPreviouslyFailedError(latest_after.error_code)


def _mark_failed(
    session: Session,
    record_id: int,
    *,
    error_code: str,
    error_message: str,
) -> None:
    now = _utc_now()
    db_started = time.perf_counter()
    stmt = (
        update(BookGeneration)
        .where(BookGeneration.id == record_id)
        .values(
            status="failed",
            finished_at=now,
            error_code=error_code,
            error_message=error_message[:200],
            updated_at=now,
        )
    )
    session.exec(stmt)
    session.commit()
    observe_ms("db.upsert_ms", (time.perf_counter() - db_started) * 1000.0, labels={"status": "failed"})


async def generate_section(
    *,
    book_id: str,
    section: str,
    force: bool = False,
    request_id: str | None = None,
    llm_client: OpenAILLMClient | None = None,
) -> dict[str, Any]:
    valid_section = _validate_section(section)
    config = get_app_config().llm
    provider = config.provider
    model = config.model

    if provider != "openai":
        raise GenerationUpstreamError("Unsupported provider")

    db_session.init_db()
    with Session(db_session.engine) as session:
        book = get_book_by_work_id(session, book_id)
        if book is None:
            openlibrary_client = OpenLibraryClient()
            try:
                book = await resolve_and_upsert_from_openlibrary(
                    session=session,
                    work_id=book_id,
                    openlibrary_client=openlibrary_client,
                )
            except (BookResolveNotFoundError, BookResolveUpstreamError) as exc:
                raise GenerationNotFoundError("Book not found") from exc

        state, row = _claim_or_observe_generation(
            session,
            book_id=book_id,
            section=valid_section,
            prompt_version=PROMPT_VERSION,
            provider=provider,
            model=model,
            schema_version=SCHEMA_VERSION_VALUE,
            force=force,
        )

        if state == "observed_complete":
            increment("cache.hit", labels={"section": valid_section, "status": "hit"})
            increment("generation.status.complete", labels={"section": valid_section, "status": "complete"})
            logger.info(
                "generation.cache.decision",
                extra={
                    "request_id": request_id,
                    "section": valid_section,
                    "work_id": book_id,
                    "status_code": 200,
                    "status": "complete",
                },
            )
            return {
                "book_id": row.book_id,
                "section": row.section,
                "prompt_version": row.prompt_version,
                "provider": row.provider,
                "model": row.model,
                "stored": True,
                "status": "complete",
                "content": row.content_json,
            }

        increment("cache.miss", labels={"section": valid_section, "status": "miss"})
        logger.info(
            "generation.cache.decision",
            extra={
                "request_id": request_id,
                "section": valid_section,
                "work_id": book_id,
                "status": "miss",
            },
        )
        client = llm_client or OpenAILLMClient(timeout_seconds=config.timeout_seconds)
        prompt = build_prompt(
            valid_section,
            _build_book_context(
                book_authors=book.authors,
                title=book.title,
                first_publish_year=book.first_publish_year,
            ),
        )
        if row.id is None:
            raise GenerationUpstreamError("Generation claim did not produce a record id")

        try:
            openai_started = time.perf_counter()
            logger.info(
                "generation.openai.start",
                extra={"request_id": request_id, "section": valid_section, "work_id": book_id},
            )
            generated = await client.generate_structured(
                model=model,
                prompt=prompt,
                json_schema=_get_json_schema(valid_section),
                temperature=config.temperature,
                max_output_tokens=config.max_output_tokens,
                request_id=request_id,
                cache_key=f"{book_id}:{valid_section}:{PROMPT_VERSION}:{provider}:{model}",
            )
            openai_latency_ms = (time.perf_counter() - openai_started) * 1000.0
            observe_ms(
                "openai.latency_ms",
                openai_latency_ms,
                labels={"section": valid_section, "model": model},
            )
            logger.info(
                "generation.openai.end",
                extra={
                    "request_id": request_id,
                    "section": valid_section,
                    "work_id": book_id,
                    "latency_ms": round(openai_latency_ms, 2),
                },
            )
            content = _parse_and_validate_content(valid_section, generated)
        except OpenAILLMClientOutputError as exc:
            increment("schema.validation_failed", labels={"section": valid_section, "status": "failed"})
            logger.exception(
                "OpenAI output validation failed",
                extra={
                    "request_id": request_id,
                    "section": valid_section,
                    "work_id": book_id,
                    "error_code": "schema_validation",
                },
            )
            _mark_failed(session, row.id, error_code="schema_validation", error_message="Invalid model output")
            raise GenerationOutputValidationError("Invalid model output") from exc
        except OpenAILLMClientTransportError as exc:
            increment("openai.error", labels={"section": valid_section, "status": "failed", "model": model})
            message = str(exc).lower()
            error_code = "timeout" if "timeout" in message else "openai_error"
            logger.exception(
                "OpenAI generation transport failure",
                extra={
                    "request_id": request_id,
                    "section": valid_section,
                    "work_id": book_id,
                    "error_code": error_code,
                },
            )
            _mark_failed(session, row.id, error_code=error_code, error_message="OpenAI request failed")
            raise GenerationUpstreamError("LLM provider unavailable") from exc
        except ValidationError as exc:
            increment("schema.validation_failed", labels={"section": valid_section, "status": "failed"})
            logger.exception(
                "Generated content schema validation failed",
                extra={
                    "request_id": request_id,
                    "section": valid_section,
                    "work_id": book_id,
                    "error_code": "schema_validation",
                },
            )
            _mark_failed(session, row.id, error_code="schema_validation", error_message="Schema validation failed")
            raise GenerationOutputValidationError("Schema validation failed") from exc
        except Exception as exc:  # pragma: no cover
            logger.exception("Unexpected generation failure")
            _mark_failed(session, row.id, error_code="unexpected", error_message="Unexpected generation failure")
            raise GenerationUpstreamError("Generation failed") from exc

        now = _utc_now()
        db_started = time.perf_counter()
        stmt = (
            update(BookGeneration)
            .where(BookGeneration.id == row.id)
            .values(
                status="complete",
                content_json=content,
                finished_at=now,
                error_code=None,
                error_message=None,
                updated_at=now,
            )
        )
        session.exec(stmt)
        session.commit()
        db_upsert_ms = (time.perf_counter() - db_started) * 1000.0
        observe_ms("db.upsert_ms", db_upsert_ms, labels={"section": valid_section, "status": "complete"})
        increment("generation.status.complete", labels={"section": valid_section, "status": "complete"})
        logger.info(
            "generation.db.upsert.complete",
            extra={
                "request_id": request_id,
                "section": valid_section,
                "work_id": book_id,
                "latency_ms": round(db_upsert_ms, 2),
            },
        )
        refreshed = session.get(BookGeneration, row.id)
        if refreshed is None:
            raise GenerationUpstreamError("Generation record not found after completion")

        return {
            "book_id": refreshed.book_id,
            "section": refreshed.section,
            "prompt_version": refreshed.prompt_version,
            "provider": refreshed.provider,
            "model": refreshed.model,
            "stored": False,
            "status": "complete",
            "content": refreshed.content_json,
        }

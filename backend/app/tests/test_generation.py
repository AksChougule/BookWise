from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, select

from app.clients.openlibrary import OpenLibraryClientError
from app.db import session as db_session
from app.db.models import Book, BookGeneration
from app.llm.prompts import PROMPT_VERSION, SCHEMA_VERSION
from app.llm.schema_utils import enforce_no_additional_properties
from app.main import app
from app.schemas.generation import ChaptersOut, CritiqueOut, KeyIdeasOut, OverviewOut


def _configure_temp_db(monkeypatch: Any, tmp_path: Any) -> None:
    db_file = tmp_path / "bookwise_generation_test.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(db_session, "engine", engine)
    db_session.init_db()


def _insert_book(book_id: str = "OL123W") -> None:
    with Session(db_session.engine) as session:
        session.add(
            Book(
                id=book_id,
                title="Test Book",
                authors="Test Author",
                first_publish_year=2000,
                cover_url=None,
                openlibrary_url=f"https://openlibrary.org/works/{book_id}",
            )
        )
        session.commit()


def _insert_generation(
    *,
    book_id: str,
    section: str,
    status: str,
    content_json: dict[str, Any] | None,
    attempt_count: int = 1,
    error_code: str | None = None,
) -> None:
    with Session(db_session.engine) as session:
        session.add(
            BookGeneration(
                book_id=book_id,
                section=section,
                status=status,
                content_json=content_json,
                provider="openai",
                model="gpt-5-mini",
                prompt_version=PROMPT_VERSION,
                schema_version=SCHEMA_VERSION,
                started_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc) if status != "pending" else None,
                error_code=error_code,
                error_message="failed" if error_code else None,
                attempt_count=attempt_count,
            )
        )
        session.commit()


def test_generation_auto_persist_then_cached(monkeypatch: Any, tmp_path: Any) -> None:
    _configure_temp_db(monkeypatch, tmp_path)
    calls = {"openai": 0}

    async def fake_get_work(self: Any, work_id: str) -> dict[str, Any]:
        return {
            "title": "The Hobbit",
            "first_publish_year": 1937,
            "authors": [{"author": {"key": "/authors/OL1A"}}],
        }

    async def fake_get_author(self: Any, author_key: str) -> dict[str, Any]:
        return {"name": "J.R.R. Tolkien"}

    class FakeLLMClient:
        def __init__(self, timeout_seconds: int | None = None) -> None:
            del timeout_seconds

        async def generate_structured(self, **kwargs: Any) -> dict[str, Any]:
            calls["openai"] += 1
            return {"overview": "A valid overview for testing output.", "reading_time_minutes": 12}

    monkeypatch.setattr("app.clients.openlibrary.OpenLibraryClient.get_work", fake_get_work)
    monkeypatch.setattr("app.clients.openlibrary.OpenLibraryClient.get_author", fake_get_author)
    monkeypatch.setattr("app.services.generation_service.OpenAILLMClient", FakeLLMClient)

    with TestClient(app) as client:
        first = client.post("/api/books/OL123W/generate/overview")
        second = client.post("/api/books/OL123W/generate/overview")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["stored"] is False
    assert second.json()["stored"] is True
    assert second.json()["status"] == "complete"
    assert calls["openai"] == 1

    with Session(db_session.engine) as session:
        assert session.get(Book, "OL123W") is not None
        rows = session.exec(select(BookGeneration).where(BookGeneration.book_id == "OL123W")).all()
        assert len(rows) == 1
        assert rows[0].status == "complete"


def test_pending_row_returns_202_and_no_openai_call(monkeypatch: Any, tmp_path: Any) -> None:
    _configure_temp_db(monkeypatch, tmp_path)
    _insert_book()
    _insert_generation(book_id="OL123W", section="overview", status="pending", content_json=None, attempt_count=1)

    calls = {"openai": 0}

    class FakeLLMClient:
        def __init__(self, timeout_seconds: int | None = None) -> None:
            del timeout_seconds

        async def generate_structured(self, **kwargs: Any) -> dict[str, Any]:
            calls["openai"] += 1
            return {"overview": "should not be called", "reading_time_minutes": 1}

    monkeypatch.setattr("app.services.generation_service.OpenAILLMClient", FakeLLMClient)

    with TestClient(app) as client:
        response = client.post("/api/books/OL123W/generate/overview")

    assert response.status_code == 202
    payload = response.json()
    assert payload["in_progress"] is True
    assert payload["retry_after_ms"] == 500
    assert calls["openai"] == 0


def test_complete_row_returns_cached_and_no_openai_call(monkeypatch: Any, tmp_path: Any) -> None:
    _configure_temp_db(monkeypatch, tmp_path)
    _insert_book()
    _insert_generation(
        book_id="OL123W",
        section="overview",
        status="complete",
        content_json={"overview": "cached", "reading_time_minutes": 9},
        attempt_count=1,
    )

    calls = {"openai": 0}

    class FakeLLMClient:
        def __init__(self, timeout_seconds: int | None = None) -> None:
            del timeout_seconds

        async def generate_structured(self, **kwargs: Any) -> dict[str, Any]:
            calls["openai"] += 1
            return {"overview": "should not run", "reading_time_minutes": 1}

    monkeypatch.setattr("app.services.generation_service.OpenAILLMClient", FakeLLMClient)

    with TestClient(app) as client:
        response = client.post("/api/books/OL123W/generate/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["stored"] is True
    assert payload["status"] == "complete"
    assert payload["content"]["overview"] == "cached"
    assert calls["openai"] == 0


def test_failed_then_force_regenerates_single_winner(monkeypatch: Any, tmp_path: Any) -> None:
    _configure_temp_db(monkeypatch, tmp_path)
    _insert_book()
    _insert_generation(
        book_id="OL123W",
        section="overview",
        status="failed",
        content_json=None,
        attempt_count=2,
        error_code="openai_error",
    )

    calls = {"openai": 0}

    class FakeLLMClient:
        def __init__(self, timeout_seconds: int | None = None) -> None:
            del timeout_seconds

        async def generate_structured(self, **kwargs: Any) -> dict[str, Any]:
            calls["openai"] += 1
            return {
                "overview": "This is a sufficiently long regenerated overview output.",
                "reading_time_minutes": 11,
            }

    monkeypatch.setattr("app.services.generation_service.OpenAILLMClient", FakeLLMClient)

    with TestClient(app) as client:
        failed = client.post("/api/books/OL123W/generate/overview")
        forced = client.post("/api/books/OL123W/generate/overview?force=true")
        cached = client.post("/api/books/OL123W/generate/overview")

    assert failed.status_code == 502
    assert failed.json()["detail"]["status"] == "failed"
    assert failed.json()["detail"]["error_code"] == "openai_error"

    assert forced.status_code == 200
    assert forced.json()["stored"] is False
    assert forced.json()["status"] == "complete"

    assert cached.status_code == 200
    assert cached.json()["stored"] is True
    assert calls["openai"] == 1

    with Session(db_session.engine) as session:
        row = session.exec(select(BookGeneration).where(BookGeneration.book_id == "OL123W")).one()
        assert row.status == "complete"
        assert row.attempt_count == 3


def test_generation_openlibrary_resolution_fails_returns_404(monkeypatch: Any, tmp_path: Any) -> None:
    _configure_temp_db(monkeypatch, tmp_path)

    async def fake_get_work(self: Any, work_id: str) -> dict[str, Any]:
        raise OpenLibraryClientError("not found", status_code=404)

    monkeypatch.setattr("app.clients.openlibrary.OpenLibraryClient.get_work", fake_get_work)

    with TestClient(app) as client:
        response = client.post("/api/books/OL999W/generate/overview")

    assert response.status_code == 404


def test_generation_invalid_output_marks_failed(monkeypatch: Any, tmp_path: Any) -> None:
    _configure_temp_db(monkeypatch, tmp_path)

    async def fake_get_work(self: Any, work_id: str) -> dict[str, Any]:
        return {
            "title": "Book Title",
            "first_publish_year": 2000,
            "authors": [{"author": {"key": "/authors/OL9A"}}],
        }

    async def fake_get_author(self: Any, author_key: str) -> dict[str, Any]:
        return {"name": "Author One"}

    class FakeLLMClient:
        def __init__(self, timeout_seconds: int | None = None) -> None:
            del timeout_seconds

        async def generate_structured(self, **kwargs: Any) -> dict[str, Any]:
            return {"bad": "payload"}

    monkeypatch.setattr("app.clients.openlibrary.OpenLibraryClient.get_work", fake_get_work)
    monkeypatch.setattr("app.clients.openlibrary.OpenLibraryClient.get_author", fake_get_author)
    monkeypatch.setattr("app.services.generation_service.OpenAILLMClient", FakeLLMClient)

    with TestClient(app) as client:
        response = client.post("/api/books/OL123W/generate/overview")

    assert response.status_code == 422

    with Session(db_session.engine) as session:
        row = session.exec(select(BookGeneration).where(BookGeneration.book_id == "OL123W")).one()
        assert row.status == "failed"
        assert row.error_code == "schema_validation"


def _assert_object_nodes_disallow_additional_properties(node: Any) -> None:
    if isinstance(node, list):
        for item in node:
            _assert_object_nodes_disallow_additional_properties(item)
        return
    if not isinstance(node, dict):
        return

    if node.get("type") == "object":
        assert node.get("additionalProperties") is False

    for value in node.values():
        _assert_object_nodes_disallow_additional_properties(value)


def test_generation_schemas_are_strict_for_openai() -> None:
    section_schemas = [
        OverviewOut.model_json_schema(),
        KeyIdeasOut.model_json_schema(),
        ChaptersOut.model_json_schema(),
        CritiqueOut.model_json_schema(),
    ]

    for schema in section_schemas:
        strict_schema = enforce_no_additional_properties(schema)
        assert strict_schema.get("type") == "object"
        assert strict_schema.get("additionalProperties") is False
        _assert_object_nodes_disallow_additional_properties(strict_schema)

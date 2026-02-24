from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session

from app.clients.openlibrary import OpenLibraryClient, OpenLibraryClientError
from app.db.models import Book


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _authors_to_storage(authors: list[str]) -> str:
    return "; ".join(author.strip() for author in authors if author.strip())


class BookResolveNotFoundError(Exception):
    pass


class BookResolveUpstreamError(Exception):
    pass


def get_book_by_work_id(session: Session, work_id: str) -> Book | None:
    return session.get(Book, work_id)


def _normalize_description(value: Any) -> str | None:
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    if isinstance(value, dict):
        dict_value = value.get("value")
        if isinstance(dict_value, str):
            normalized = dict_value.strip()
            return normalized or None
    return None


def _extract_first_publish_year(work_payload: dict[str, Any]) -> int | None:
    value = work_payload.get("first_publish_year")
    if isinstance(value, int):
        return value
    date_value = work_payload.get("first_publish_date")
    if isinstance(date_value, str) and len(date_value) >= 4 and date_value[:4].isdigit():
        return int(date_value[:4])
    return None


def _author_keys_from_work(work_payload: dict[str, Any]) -> list[str]:
    authors = work_payload.get("authors")
    if not isinstance(authors, list):
        return []

    keys: list[str] = []
    for entry in authors:
        if not isinstance(entry, dict):
            continue
        author_ref = entry.get("author")
        if not isinstance(author_ref, dict):
            continue
        key = author_ref.get("key")
        if isinstance(key, str) and key.startswith("/authors/"):
            keys.append(key)
        if len(keys) >= 3:
            break
    return keys


async def resolve_work_metadata(
    work_id: str,
    openlibrary_client: OpenLibraryClient | None = None,
) -> dict[str, Any]:
    client = openlibrary_client or OpenLibraryClient()

    try:
        work_payload = await client.get_work(work_id)
    except OpenLibraryClientError as exc:
        if exc.status_code == 404:
            raise BookResolveNotFoundError("Book not found") from exc
        raise BookResolveUpstreamError("Open Library unavailable") from exc

    author_names: list[str] = []
    for author_key in _author_keys_from_work(work_payload):
        try:
            author_payload = await client.get_author(author_key)
        except OpenLibraryClientError:
            continue
        name = author_payload.get("name")
        if isinstance(name, str) and name.strip():
            author_names.append(name.strip())

    covers = work_payload.get("covers")
    cover_url = None
    if isinstance(covers, list) and covers and isinstance(covers[0], int):
        cover_url = f"https://covers.openlibrary.org/b/id/{covers[0]}-L.jpg"

    subjects = work_payload.get("subjects")
    normalized_subjects = [str(subject) for subject in subjects] if isinstance(subjects, list) else []

    title = work_payload.get("title")
    normalized_title = str(title) if title else ""
    openlibrary_url = f"https://openlibrary.org/works/{work_id}"

    return {
        "id": work_id,
        "title": normalized_title,
        "authors": author_names,
        "description": _normalize_description(work_payload.get("description")),
        "subjects": normalized_subjects,
        "cover_url": cover_url,
        "openlibrary_url": openlibrary_url,
        "first_publish_year": _extract_first_publish_year(work_payload),
        "resolved_from": "work_id",
    }


async def resolve_and_upsert_from_openlibrary(
    session: Session,
    work_id: str,
    metadata: dict[str, Any] | None = None,
    openlibrary_client: OpenLibraryClient | None = None,
) -> Book:
    normalized_metadata = metadata or await resolve_work_metadata(
        work_id=work_id, openlibrary_client=openlibrary_client
    )
    return upsert_book(
        session,
        {
            "id": normalized_metadata["id"],
            "title": normalized_metadata["title"],
            "authors": normalized_metadata["authors"],
            "first_publish_year": normalized_metadata["first_publish_year"],
            "cover_url": normalized_metadata["cover_url"],
            "openlibrary_url": normalized_metadata["openlibrary_url"],
        },
    )


def upsert_book(session: Session, book_data: dict[str, Any]) -> Book:
    book_id = str(book_data["id"])
    existing = session.get(Book, book_id)

    if existing is None:
        existing = Book(
            id=book_id,
            title=str(book_data["title"]),
            authors=_authors_to_storage(book_data.get("authors", [])),
            first_publish_year=book_data.get("first_publish_year"),
            cover_url=book_data.get("cover_url"),
            openlibrary_url=str(book_data["openlibrary_url"]),
        )
    else:
        existing.title = str(book_data["title"])
        existing.authors = _authors_to_storage(book_data.get("authors", []))
        existing.first_publish_year = book_data.get("first_publish_year")
        existing.cover_url = book_data.get("cover_url")
        existing.openlibrary_url = str(book_data["openlibrary_url"])
        existing.updated_at = _utc_now()

    session.add(existing)
    session.commit()
    session.refresh(existing)
    return existing

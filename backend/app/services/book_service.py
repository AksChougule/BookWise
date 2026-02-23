from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session

from app.db.models import Book


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _authors_to_storage(authors: list[str]) -> str:
    return "; ".join(author.strip() for author in authors if author.strip())


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

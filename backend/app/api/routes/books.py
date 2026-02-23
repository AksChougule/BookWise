import re
from typing import Any

from fastapi import APIRouter, HTTPException, Path
from sqlmodel import Session

from app.clients.openlibrary import OpenLibraryClient, OpenLibraryClientError
from app.db import session as db_session
from app.services.book_service import upsert_book


router = APIRouter()
openlibrary_client = OpenLibraryClient()
WORK_ID_PATTERN = re.compile(r"^OL[0-9]+W$")


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


@router.get("/books/{work_id}")
async def get_book(work_id: str = Path(pattern=r"^OL[0-9]+W$")) -> dict[str, Any]:
    if WORK_ID_PATTERN.fullmatch(work_id) is None:
        raise HTTPException(status_code=422, detail="Invalid work_id format")

    try:
        work_payload = await openlibrary_client.get_work(work_id)
    except OpenLibraryClientError as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail="Book not found")
        raise HTTPException(status_code=502, detail="Open Library is unavailable")

    author_names: list[str] = []
    for author_key in _author_keys_from_work(work_payload):
        try:
            author_payload = await openlibrary_client.get_author(author_key)
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

    normalized = {
        "id": work_id,
        "title": normalized_title,
        "authors": author_names,
        "description": _normalize_description(work_payload.get("description")),
        "subjects": normalized_subjects,
        "cover_url": cover_url,
        "openlibrary_url": openlibrary_url,
        "resolved_from": "work_id",
    }

    db_session.init_db()
    with Session(db_session.engine) as session:
        upsert_book(
            session,
            {
                "id": normalized["id"],
                "title": normalized["title"],
                "authors": normalized["authors"],
                "first_publish_year": _extract_first_publish_year(work_payload),
                "cover_url": normalized["cover_url"],
                "openlibrary_url": normalized["openlibrary_url"],
            },
        )

    return normalized

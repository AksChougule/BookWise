import re
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.clients.openlibrary import OpenLibraryClient, OpenLibraryClientError
from app.services import curated_service


router = APIRouter()
openlibrary_client = OpenLibraryClient()
WORK_ID_PATTERN = re.compile(r"^OL[0-9]+W$")
MAX_STRICT_ATTEMPTS = 5


def _is_english(language_values: Any) -> bool:
    if not isinstance(language_values, list):
        return False
    normalized = {str(value).strip().lower() for value in language_values}
    return "en" in normalized or "eng" in normalized


def _extract_work_id(key: Any) -> str | None:
    if not isinstance(key, str) or not key.startswith("/works/"):
        return None
    candidate = key.removeprefix("/works/")
    if WORK_ID_PATTERN.fullmatch(candidate):
        return candidate
    return None


def _normalize_text(value: Any) -> str:
    return str(value).strip().lower()


async def _resolve_curated_work_id(title: str, author: str) -> str | None:
    docs = await openlibrary_client.search_books(query=f"{title} {author}", limit=25)
    title_target = _normalize_text(title)
    author_target = _normalize_text(author)

    best_candidate: tuple[int, str] | None = None
    for doc in docs:
        if not _is_english(doc.get("language")):
            continue
        work_id = _extract_work_id(doc.get("key"))
        if work_id is None:
            continue

        doc_title = _normalize_text(doc.get("title"))
        doc_authors_raw = doc.get("author_name")
        doc_authors = (
            [_normalize_text(author_name) for author_name in doc_authors_raw]
            if isinstance(doc_authors_raw, list)
            else []
        )
        title_exact = int(doc_title == title_target)
        author_exact = int(any(name == author_target for name in doc_authors))
        author_partial = int(any(author_target in name or name in author_target for name in doc_authors))
        score = (title_exact * 4) + (author_exact * 3) + (author_partial * 2) + 1

        if title_exact and author_exact:
            return work_id
        if best_candidate is None or score > best_candidate[0]:
            best_candidate = (score, work_id)

    if best_candidate is not None:
        return best_candidate[1]
    return None


@router.get("/curated/random")
async def get_random_curated(strict: bool = Query(default=True)) -> dict[str, str | None]:
    try:
        books = curated_service.load_curated_books()
    except (OSError, ValueError):
        raise HTTPException(status_code=500, detail="Curated books are unavailable")

    if not books:
        raise HTTPException(status_code=500, detail="Curated books are unavailable")

    remaining_books = books.copy()
    attempts = min(MAX_STRICT_ATTEMPTS, len(remaining_books)) if strict else 1

    for _ in range(attempts):
        selected = curated_service.get_random_curated_book(remaining_books)
        remaining_books.remove(selected)

        work_id = selected.get("work_id")
        if isinstance(work_id, str) and WORK_ID_PATTERN.fullmatch(work_id):
            return {
                "id": work_id,
                "source": "curated_list",
                "title": selected["title"],
                "author": selected["author"],
            }

        try:
            resolved_work_id = await _resolve_curated_work_id(
                title=selected["title"],
                author=selected["author"],
            )
        except OpenLibraryClientError:
            raise HTTPException(status_code=502, detail="Could not resolve curated book id")

        if resolved_work_id is not None:
            selected["work_id"] = resolved_work_id
            curated_service.save_curated_books(books)
            return {
                "id": resolved_work_id,
                "source": "curated_list",
                "title": selected["title"],
                "author": selected["author"],
            }

        if not strict:
            return {
                "id": None,
                "source": "curated_list",
                "title": selected["title"],
                "author": selected["author"],
            }

    raise HTTPException(status_code=502, detail="Could not resolve curated book id")

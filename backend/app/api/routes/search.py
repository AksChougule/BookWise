from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from app.clients.openlibrary import OpenLibraryClient, OpenLibraryClientError
from app.middleware.rate_limit import limiter


router = APIRouter()
openlibrary_client = OpenLibraryClient()


def _extract_work_id(key: str | None) -> str | None:
    if not key:
        return None
    if not key.startswith("/works/"):
        return None
    candidate = key.removeprefix("/works/")
    if candidate.startswith("OL") and candidate.endswith("W"):
        return candidate
    return None


def _is_english(language_values: Any) -> bool:
    if not isinstance(language_values, list):
        return False
    normalized = {str(value).strip().lower() for value in language_values}
    return "en" in normalized or "eng" in normalized


@router.get("/search")
@limiter.limit("60/minute")
async def search_books(
    request: Request,
    q: str = Query(min_length=2, max_length=120),
    limit: int = Query(default=25, ge=1, le=100),
) -> dict[str, Any]:
    del request  # required by slowapi decorator
    try:
        raw_docs = await openlibrary_client.search_books(query=q, limit=limit)
    except OpenLibraryClientError:
        raise HTTPException(status_code=502, detail="Open Library is unavailable")

    normalized_results: list[dict[str, Any]] = []
    for doc in raw_docs:
        language = doc.get("language")
        if not _is_english(language):
            continue

        work_id = _extract_work_id(doc.get("key"))
        if work_id is None:
            continue

        cover_id = doc.get("cover_i")
        cover_url = None
        if isinstance(cover_id, int):
            cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"

        authors = doc.get("author_name")
        if not isinstance(authors, list):
            authors = []

        first_publish_year = doc.get("first_publish_year")
        if not isinstance(first_publish_year, int):
            first_publish_year = None

        normalized_results.append(
            {
                "id": work_id,
                "title": str(doc.get("title") or ""),
                "authors": [str(author) for author in authors],
                "first_publish_year": first_publish_year,
                "language": [str(lang) for lang in language],
                "cover_url": cover_url,
            }
        )

    return {"query": q, "results": normalized_results}

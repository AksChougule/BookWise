import re
from typing import Any

from fastapi import APIRouter, HTTPException, Path
from sqlmodel import Session

from app.clients.openlibrary import OpenLibraryClient
from app.db import session as db_session
from app.services.book_service import (
    BookResolveNotFoundError,
    BookResolveUpstreamError,
    resolve_and_upsert_from_openlibrary,
    resolve_work_metadata,
)


router = APIRouter()
openlibrary_client = OpenLibraryClient()
WORK_ID_PATTERN = re.compile(r"^OL[0-9]+W$")


@router.get("/books/{work_id}")
async def get_book(work_id: str = Path(pattern=r"^OL[0-9]+W$")) -> dict[str, Any]:
    if WORK_ID_PATTERN.fullmatch(work_id) is None:
        raise HTTPException(status_code=422, detail="Invalid work_id format")

    try:
        metadata = await resolve_work_metadata(work_id=work_id, openlibrary_client=openlibrary_client)
    except BookResolveNotFoundError:
        raise HTTPException(status_code=404, detail="Book not found")
    except BookResolveUpstreamError:
        raise HTTPException(status_code=502, detail="Open Library is unavailable")

    db_session.init_db()
    with Session(db_session.engine) as session:
        await resolve_and_upsert_from_openlibrary(
            session=session,
            work_id=work_id,
            metadata=metadata,
            openlibrary_client=openlibrary_client,
        )

    return {
        "id": metadata["id"],
        "title": metadata["title"],
        "authors": metadata["authors"],
        "description": metadata["description"],
        "subjects": metadata["subjects"],
        "cover_url": metadata["cover_url"],
        "openlibrary_url": metadata["openlibrary_url"],
        "resolved_from": metadata["resolved_from"],
    }

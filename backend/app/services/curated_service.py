import os
import tempfile
from pathlib import Path
from typing import Any, TypedDict

import yaml


class CuratedBook(TypedDict):
    title: str
    author: str
    work_id: str | None


CURATED_FILE_PATH = Path(__file__).resolve().parents[3] / "data" / "curated_books.yml"


def _validate_books_payload(payload: Any) -> list[CuratedBook]:
    if not isinstance(payload, dict):
        raise ValueError("Invalid curated books format")
    books = payload.get("books")
    if not isinstance(books, list):
        raise ValueError("Invalid curated books format")

    normalized_books: list[CuratedBook] = []
    for entry in books:
        if not isinstance(entry, dict):
            raise ValueError("Invalid curated book entry")
        title = entry.get("title")
        author = entry.get("author")
        work_id = entry.get("work_id")
        if not isinstance(title, str) or not isinstance(author, str):
            raise ValueError("Invalid curated book entry")
        if work_id is not None and not isinstance(work_id, str):
            raise ValueError("Invalid curated book entry")
        normalized_books.append({"title": title, "author": author, "work_id": work_id})
    return normalized_books


def load_curated_books() -> list[CuratedBook]:
    raw = CURATED_FILE_PATH.read_text(encoding="utf-8")
    payload = yaml.safe_load(raw)
    return _validate_books_payload(payload)


def get_random_curated_book(books: list[CuratedBook] | None = None) -> CuratedBook:
    import random

    source = books if books is not None else load_curated_books()
    if not source:
        raise ValueError("No curated books available")
    return random.choice(source)


def save_curated_books(updated_books: list[CuratedBook]) -> None:
    validated_books = _validate_books_payload({"books": updated_books})
    payload = {"books": validated_books}
    target_path = CURATED_FILE_PATH

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        delete=False,
        dir=target_path.parent,
        suffix=".tmp",
    ) as tmp:
        yaml.safe_dump(payload, tmp, sort_keys=False, allow_unicode=True)
        temp_path = Path(tmp.name)

    os.replace(temp_path, target_path)

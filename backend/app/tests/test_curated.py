from pathlib import Path
from typing import Any

import yaml
from fastapi.testclient import TestClient

from app.main import app
from app.services import curated_service


def test_curated_random_returns_existing_work_id(monkeypatch: Any) -> None:
    books = [{"title": "Book A", "author": "Author A", "work_id": "OL123W"}]

    monkeypatch.setattr("app.api.routes.curated.curated_service.load_curated_books", lambda: books)
    monkeypatch.setattr(
        "app.api.routes.curated.curated_service.get_random_curated_book",
        lambda source: source[0],
    )

    with TestClient(app) as client:
        response = client.get("/api/curated/random")

    assert response.status_code == 200
    assert response.json() == {
        "id": "OL123W",
        "source": "curated_list",
        "title": "Book A",
        "author": "Author A",
    }


def test_curated_random_resolves_missing_work_id(monkeypatch: Any) -> None:
    books = [{"title": "Book A", "author": "Author A", "work_id": None}]
    saved_books: list[dict[str, Any]] = []

    async def fake_search_books(query: str, limit: int) -> list[dict[str, Any]]:
        assert query == "Book A Author A"
        assert limit == 25
        return [
            {
                "key": "/works/OL999W",
                "title": "Book A",
                "author_name": ["Author A"],
                "language": ["eng"],
            }
        ]

    monkeypatch.setattr("app.api.routes.curated.curated_service.load_curated_books", lambda: books)
    monkeypatch.setattr(
        "app.api.routes.curated.curated_service.get_random_curated_book",
        lambda source: source[0],
    )
    monkeypatch.setattr(
        "app.api.routes.curated.curated_service.save_curated_books",
        lambda updated: saved_books.extend(updated),
    )
    monkeypatch.setattr("app.api.routes.curated.openlibrary_client.search_books", fake_search_books)

    with TestClient(app) as client:
        response = client.get("/api/curated/random")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "OL999W"
    assert books[0]["work_id"] == "OL999W"
    assert saved_books[0]["work_id"] == "OL999W"


def test_curated_random_strict_retries_then_502(monkeypatch: Any) -> None:
    books = [
        {"title": "Book 1", "author": "Author 1", "work_id": None},
        {"title": "Book 2", "author": "Author 2", "work_id": None},
        {"title": "Book 3", "author": "Author 3", "work_id": None},
        {"title": "Book 4", "author": "Author 4", "work_id": None},
        {"title": "Book 5", "author": "Author 5", "work_id": None},
    ]
    picks = {"count": 0}

    async def fake_search_books(query: str, limit: int) -> list[dict[str, Any]]:
        return []

    def fake_picker(source: list[dict[str, Any]]) -> dict[str, Any]:
        picks["count"] += 1
        return source[0]

    monkeypatch.setattr("app.api.routes.curated.curated_service.load_curated_books", lambda: books)
    monkeypatch.setattr("app.api.routes.curated.curated_service.get_random_curated_book", fake_picker)
    monkeypatch.setattr("app.api.routes.curated.openlibrary_client.search_books", fake_search_books)

    with TestClient(app) as client:
        response = client.get("/api/curated/random?strict=true")

    assert response.status_code == 502
    assert response.json()["detail"] == "Could not resolve curated book id"
    assert picks["count"] == 5


def test_curated_random_non_strict_returns_null_id(monkeypatch: Any) -> None:
    books = [{"title": "Book A", "author": "Author A", "work_id": None}]

    async def fake_search_books(query: str, limit: int) -> list[dict[str, Any]]:
        return []

    monkeypatch.setattr("app.api.routes.curated.curated_service.load_curated_books", lambda: books)
    monkeypatch.setattr(
        "app.api.routes.curated.curated_service.get_random_curated_book",
        lambda source: source[0],
    )
    monkeypatch.setattr("app.api.routes.curated.openlibrary_client.search_books", fake_search_books)

    with TestClient(app) as client:
        response = client.get("/api/curated/random?strict=false")

    assert response.status_code == 200
    assert response.json() == {
        "id": None,
        "source": "curated_list",
        "title": "Book A",
        "author": "Author A",
    }


def test_save_curated_books_atomic_write(tmp_path: Any, monkeypatch: Any) -> None:
    target_path = Path(tmp_path) / "curated_books.yml"
    monkeypatch.setattr(curated_service, "CURATED_FILE_PATH", target_path)

    curated_service.save_curated_books(
        [{"title": "New Book", "author": "Author", "work_id": "OL1W"}]
    )

    assert target_path.exists()
    content = yaml.safe_load(target_path.read_text(encoding="utf-8"))
    assert content == {"books": [{"title": "New Book", "author": "Author", "work_id": "OL1W"}]}

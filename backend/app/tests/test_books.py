from typing import Any

from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, select

from app.db.models import Book
from app.db import session as db_session
from app.main import app


def _configure_temp_db(monkeypatch: Any, tmp_path: Any) -> None:
    db_file = tmp_path / "bookwise_test.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(db_session, "engine", engine)
    db_session.init_db()


def test_get_book_returns_metadata_and_persists(monkeypatch: Any, tmp_path: Any) -> None:
    _configure_temp_db(monkeypatch, tmp_path)

    async def fake_get_work(work_id: str) -> dict[str, Any]:
        assert work_id == "OL123W"
        return {
            "title": "The Hobbit",
            "description": {"value": "A classic fantasy novel."},
            "subjects": ["Fantasy", "Adventure"],
            "covers": [12345],
            "first_publish_year": 1937,
            "authors": [
                {"author": {"key": "/authors/OL1A"}},
                {"author": {"key": "/authors/OL2A"}},
            ],
        }

    async def fake_get_author(author_key: str) -> dict[str, Any]:
        mapping = {
            "/authors/OL1A": {"name": "J.R.R. Tolkien"},
            "/authors/OL2A": {"name": "Another Author"},
        }
        return mapping[author_key]

    monkeypatch.setattr("app.api.routes.books.openlibrary_client.get_work", fake_get_work)
    monkeypatch.setattr("app.api.routes.books.openlibrary_client.get_author", fake_get_author)

    with TestClient(app) as client:
        response = client.get("/api/books/OL123W")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {
        "id",
        "title",
        "authors",
        "description",
        "subjects",
        "cover_url",
        "openlibrary_url",
        "resolved_from",
    }
    assert payload["id"] == "OL123W"
    assert payload["openlibrary_url"] == "https://openlibrary.org/works/OL123W"
    assert payload["cover_url"] == "https://covers.openlibrary.org/b/id/12345-L.jpg"
    assert payload["resolved_from"] == "work_id"

    with Session(db_session.engine) as session:
        persisted = session.get(Book, "OL123W")
        assert persisted is not None
        assert persisted.title == "The Hobbit"
        assert persisted.authors == "J.R.R. Tolkien; Another Author"


def test_get_book_upsert_keeps_single_row(monkeypatch: Any, tmp_path: Any) -> None:
    _configure_temp_db(monkeypatch, tmp_path)

    async def fake_get_work(work_id: str) -> dict[str, Any]:
        return {
            "title": "Book Title",
            "description": "desc",
            "subjects": [],
            "covers": [1],
            "first_publish_year": 2000,
            "authors": [{"author": {"key": "/authors/OL9A"}}],
        }

    async def fake_get_author(author_key: str) -> dict[str, Any]:
        return {"name": "Author One"}

    monkeypatch.setattr("app.api.routes.books.openlibrary_client.get_work", fake_get_work)
    monkeypatch.setattr("app.api.routes.books.openlibrary_client.get_author", fake_get_author)

    with TestClient(app) as client:
        first = client.get("/api/books/OL123W")
        second = client.get("/api/books/OL123W")

    assert first.status_code == 200
    assert second.status_code == 200

    with Session(db_session.engine) as session:
        rows = session.exec(select(Book).where(Book.id == "OL123W")).all()
        assert len(rows) == 1


def test_get_book_invalid_work_id_returns_422(tmp_path: Any, monkeypatch: Any) -> None:
    _configure_temp_db(monkeypatch, tmp_path)

    with TestClient(app) as client:
        response = client.get("/api/books/not-a-work-id")

    assert response.status_code == 422

from typing import Any

from fastapi.testclient import TestClient

from app.main import app


def test_search_valid_normalized_response(monkeypatch: Any) -> None:
    async def fake_search_books(query: str, limit: int) -> list[dict[str, Any]]:
        assert query == "hobbit"
        assert limit == 25
        return [
            {
                "key": "/works/OL123W",
                "title": "The Hobbit",
                "author_name": ["J.R.R. Tolkien"],
                "first_publish_year": 1937,
                "language": ["eng"],
                "cover_i": 12345,
            }
        ]

    monkeypatch.setattr("app.api.routes.search.openlibrary_client.search_books", fake_search_books)

    with TestClient(app) as client:
        response = client.get("/api/search", params={"q": "hobbit"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "hobbit"
    assert len(payload["results"]) == 1
    result = payload["results"][0]
    assert set(result.keys()) == {
        "id",
        "title",
        "authors",
        "first_publish_year",
        "language",
        "cover_url",
    }
    assert result["id"] == "OL123W"
    assert result["title"] == "The Hobbit"
    assert result["authors"] == ["J.R.R. Tolkien"]
    assert result["first_publish_year"] == 1937
    assert result["language"] == ["eng"]
    assert result["cover_url"] == "https://covers.openlibrary.org/b/id/12345-M.jpg"


def test_search_filters_non_english(monkeypatch: Any) -> None:
    async def fake_search_books(query: str, limit: int) -> list[dict[str, Any]]:
        return [
            {
                "key": "/works/OL111W",
                "title": "English Book",
                "author_name": ["A"],
                "language": ["en"],
            },
            {
                "key": "/works/OL222W",
                "title": "French Book",
                "author_name": ["B"],
                "language": ["fr"],
            },
            {
                "key": "/works/OL333W",
                "title": "Unknown Language",
                "author_name": ["C"],
            },
        ]

    monkeypatch.setattr("app.api.routes.search.openlibrary_client.search_books", fake_search_books)

    with TestClient(app) as client:
        response = client.get("/api/search", params={"q": "book"})

    assert response.status_code == 200
    payload = response.json()
    assert [item["id"] for item in payload["results"]] == ["OL111W"]


def test_search_rejects_short_query() -> None:
    with TestClient(app) as client:
        response = client.get("/api/search", params={"q": "a"})

    assert response.status_code == 422


def test_search_rejects_limit_over_max() -> None:
    with TestClient(app) as client:
        response = client.get("/api/search", params={"q": "hobbit", "limit": 500})

    assert response.status_code == 422

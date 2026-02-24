from __future__ import annotations

import json
import re
from typing import Any

from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine

from app.db import session as db_session
from app.observability.logging import JsonFormatter
from app.observability.metrics import reset
from app.main import app


UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _configure_temp_db(monkeypatch: Any, tmp_path: Any) -> None:
    db_file = tmp_path / "bookwise_obs_test.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(db_session, "engine", engine)
    db_session.init_db()


def _mock_generation_dependencies(monkeypatch: Any) -> None:
    async def fake_get_work(self: Any, work_id: str) -> dict[str, Any]:
        return {
            "title": "The Hobbit",
            "first_publish_year": 1937,
            "authors": [{"author": {"key": "/authors/OL1A"}}],
        }

    async def fake_get_author(self: Any, author_key: str) -> dict[str, Any]:
        return {"name": "J.R.R. Tolkien"}

    class FakeLLMClient:
        def __init__(self, timeout_seconds: int | None = None) -> None:
            del timeout_seconds

        async def generate_structured(self, **kwargs: Any) -> dict[str, Any]:
            return {"overview": "A valid overview for testing output.", "reading_time_minutes": 12}

    monkeypatch.setattr("app.clients.openlibrary.OpenLibraryClient.get_work", fake_get_work)
    monkeypatch.setattr("app.clients.openlibrary.OpenLibraryClient.get_author", fake_get_author)
    monkeypatch.setattr("app.services.generation_service.OpenAILLMClient", FakeLLMClient)


def test_request_id_passthrough_header() -> None:
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": "abc"})

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == "abc"


def test_request_id_generated_when_missing() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    request_id = response.headers.get("X-Request-ID")
    assert request_id is not None
    assert UUID_RE.match(request_id) is not None


def test_metrics_cache_hit_miss_and_openai_latency(monkeypatch: Any, tmp_path: Any) -> None:
    reset()
    _configure_temp_db(monkeypatch, tmp_path)
    _mock_generation_dependencies(monkeypatch)

    with TestClient(app) as client:
        first = client.post("/api/books/OL123W/generate/overview")
        second = client.post("/api/books/OL123W/generate/overview")
        metrics = client.get("/metrics")

    assert first.status_code == 200
    assert second.status_code == 200
    assert metrics.status_code == 200

    payload = metrics.json()
    counters = payload["counters"]
    timers = payload["timers_ms"]

    assert counters.get("cache.miss{section=overview,status=miss}", 0) >= 1
    assert counters.get("cache.hit{section=overview,status=hit}", 0) >= 1
    assert "openai.latency_ms{model=gpt-5-mini,section=overview}" in timers


def test_generation_logs_include_request_id_and_single_cache_key(monkeypatch: Any, tmp_path: Any, caplog: Any) -> None:
    reset()
    _configure_temp_db(monkeypatch, tmp_path)
    _mock_generation_dependencies(monkeypatch)
    caplog.set_level("INFO")

    formatter = JsonFormatter()

    with TestClient(app) as client:
        response = client.post(
            "/api/books/OL123W/generate/overview",
            headers={"X-Request-ID": "req-123"},
        )

    assert response.status_code == 200

    json_logs: list[dict[str, Any]] = []
    for record in caplog.records:
        if record.name.startswith("app."):
            try:
                json_logs.append(json.loads(formatter.format(record)))
            except json.JSONDecodeError:
                continue

    assert any(log.get("request_id") == "req-123" for log in json_logs)
    assert any(log.get("message") == "generation.request.start" for log in json_logs)

    cache_key_occurrences = [
        log for log in json_logs if log.get("request_id") == "req-123" and "cache_key" in log
    ]
    assert len(cache_key_occurrences) == 1
    assert cache_key_occurrences[0]["cache_key"] == "OL123W:overview"

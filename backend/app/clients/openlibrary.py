import os
from typing import Any

import httpx


class OpenLibraryClientError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class OpenLibraryClient:
    def __init__(self, base_url: str | None = None, timeout_seconds: float = 10.0) -> None:
        self._base_url = base_url or os.getenv("OPENLIBRARY_BASE_URL", "https://openlibrary.org")
        self._timeout = httpx.Timeout(timeout_seconds)

    async def _get_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as client:
                response = await client.get(path, params=params)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise OpenLibraryClientError("Open Library request failed", status_code=exc.response.status_code) from exc
        except httpx.RequestError as exc:
            raise OpenLibraryClientError("Open Library is unavailable") from exc

        if isinstance(payload, dict):
            return payload
        return {}

    async def search_books(self, query: str, limit: int) -> list[dict[str, Any]]:
        payload = await self._get_json("/search.json", params={"q": query, "limit": limit})
        docs = payload.get("docs", [])
        if not isinstance(docs, list):
            return []
        return [doc for doc in docs if isinstance(doc, dict)]

    async def get_work(self, work_id: str) -> dict[str, Any]:
        return await self._get_json(f"/works/{work_id}.json")

    async def get_author(self, author_key: str) -> dict[str, Any]:
        return await self._get_json(f"{author_key}.json")

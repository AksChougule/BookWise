#!/usr/bin/env python3
"""
Resolve Open Library Work IDs for curated_books.yml entries.

- Reads ../../data/curated_books.yml
- For each entry with work_id null, calls Open Library search
- Picks best English match based on title+author scoring
- Writes file back in-place
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import httpx

try:
    import yaml  # type: ignore
except ImportError as e:
    raise SystemExit(
        "Missing dependency: PyYAML.\n"
        "Install it (dev-only) from backend/:  poetry add --group dev pyyaml"
    ) from e


OPENLIBRARY_BASE_URL = "https://openlibrary.org"
COVERS_BASE_URL = "https://covers.openlibrary.org"


@dataclass
class Candidate:
    work_id: str
    title: str
    authors: list[str]
    language: list[str]
    score: int


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _extract_work_id(key: Optional[str]) -> Optional[str]:
    # key usually like "/works/OL123W"
    if not key:
        return None
    m = re.search(r"/works/(OL\d+W)", key)
    return m.group(1) if m else None


def _is_english(languages: Any) -> bool:
    if not languages:
        return False
    if isinstance(languages, str):
        langs = [_norm(languages)]
    elif isinstance(languages, list):
        langs = [_norm(str(x)) for x in languages]
    else:
        langs = [_norm(str(languages))]
    return any(l in ("en", "eng") for l in langs)


def _score_candidate(
    *,
    doc_title: str,
    doc_authors: list[str],
    target_title: str,
    target_author: str,
) -> int:
    """
    Simple heuristic scoring.
    Higher is better.
    """
    score = 0

    dt = _norm(doc_title)
    tt = _norm(target_title)
    ta = _norm(target_author)

    # Title match weighting
    if dt == tt:
        score += 80
    elif tt in dt or dt in tt:
        score += 50
    else:
        # token overlap
        dt_tokens = set(dt.split(" "))
        tt_tokens = set(tt.split(" "))
        overlap = len(dt_tokens & tt_tokens)
        score += min(30, overlap * 5)

    # Author match weighting
    authors_norm = [_norm(a) for a in doc_authors if a]
    if authors_norm:
        if any(a == ta for a in authors_norm):
            score += 40
        elif any(ta in a or a in ta for a in authors_norm):
            score += 25

    return score


async def _search_openlibrary(
    client: httpx.AsyncClient, query: str, limit: int = 10
) -> list[dict[str, Any]]:
    url = f"{OPENLIBRARY_BASE_URL}/search.json"
    resp = await client.get(url, params={"q": query, "limit": limit})
    resp.raise_for_status()
    data = resp.json()
    docs = data.get("docs", [])
    if not isinstance(docs, list):
        return []
    return docs


def _pick_best_work_id(
    docs: list[dict[str, Any]], *, title: str, author: str
) -> Optional[str]:
    candidates: list[Candidate] = []

    for d in docs:
        # strict English-only
        if not _is_english(d.get("language")):
            continue

        work_id = _extract_work_id(d.get("key"))
        if not work_id:
            continue

        doc_title = str(d.get("title") or "").strip()
        doc_authors = d.get("author_name") or []
        if not isinstance(doc_authors, list):
            doc_authors = [str(doc_authors)]
        doc_authors = [str(a) for a in doc_authors if a]

        if not doc_title:
            continue

        score = _score_candidate(
            doc_title=doc_title,
            doc_authors=doc_authors,
            target_title=title,
            target_author=author,
        )

        # small bonus if first publish year exists (often higher quality)
        if d.get("first_publish_year"):
            score += 5

        candidates.append(
            Candidate(
                work_id=work_id,
                title=doc_title,
                authors=doc_authors,
                language=[str(x) for x in (d.get("language") or [])],
                score=score,
            )
        )

    if not candidates:
        return None

    candidates.sort(key=lambda c: c.score, reverse=True)
    best = candidates[0]

    # require a minimum confidence threshold to avoid wrong matches
    if best.score < 70:
        return None

    return best.work_id


async def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]  # backend/scripts -> repo root
    yml_path = repo_root / "data" / "curated_books.yml"
    if not yml_path.exists():
        raise SystemExit(f"Could not find {yml_path}")

    raw = yml_path.read_text(encoding="utf-8")
    parsed = yaml.safe_load(raw)
    if not isinstance(parsed, dict) or "books" not in parsed:
        raise SystemExit("Invalid YAML format: expected top-level key 'books'")

    books = parsed["books"]
    if not isinstance(books, list):
        raise SystemExit("Invalid YAML format: 'books' must be a list")

    to_resolve = [b for b in books if isinstance(b, dict) and not b.get("work_id")]
    print(f"Loaded {len(books)} books. Need to resolve {len(to_resolve)} work_ids.")

    timeout = httpx.Timeout(10.0, connect=10.0)
    headers = {"User-Agent": "BookWise/0.1 (work-id resolver)"}

    successes = 0
    failures: list[tuple[str, str]] = []

    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        for idx, b in enumerate(books):
            if not isinstance(b, dict):
                continue
            if b.get("work_id"):
                continue

            title = str(b.get("title") or "").strip()
            author = str(b.get("author") or "").strip()
            if not title or not author:
                failures.append((title or "<missing title>", "missing title/author"))
                continue

            q = f'title:"{title}" author:"{author}"'
            try:
                docs = await _search_openlibrary(client, q, limit=10)
                work_id = _pick_best_work_id(docs, title=title, author=author)
                if not work_id:
                    # fallback: broader query if strict query fails
                    q2 = f"{title} {author}"
                    docs2 = await _search_openlibrary(client, q2, limit=10)
                    work_id = _pick_best_work_id(docs2, title=title, author=author)

                if work_id:
                    b["work_id"] = work_id
                    successes += 1
                    print(f"[OK] {title} — {author} -> {work_id}")
                else:
                    failures.append((title, "no confident match"))
                    print(f"[NO MATCH] {title} — {author}")

            except httpx.HTTPStatusError as e:
                failures.append((title, f"http status {e.response.status_code}"))
                print(f"[ERROR] {title} — {author}: HTTP {e.response.status_code}")
            except httpx.RequestError as e:
                failures.append((title, "network error"))
                print(f"[ERROR] {title} — {author}: network error: {e}")

            # Be polite to the public API
            time.sleep(0.2)

    # Write back YAML (keep it simple + readable)
    yml_path.write_text(
        yaml.safe_dump(parsed, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    print("\n=== Summary ===")
    print(f"Resolved: {successes}")
    print(f"Failed:   {len(failures)}")
    if failures:
        print("\nFailures:")
        for title, reason in failures[:30]:
            print(f" - {title}: {reason}")
        if len(failures) > 30:
            print(f" ... and {len(failures) - 30} more")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
# BookWise v2 PRD (Implementation-Ready, AI-Friendly)

## 1) Product Summary

BookWise is a web app that helps users discover books and generate structured learning insights with a persistence-first backend.

Primary user jobs:
- Find English books quickly.
- Get curated random suggestions.
- Open a book detail page with metadata.
- Generate structured sections (`overview`, `key_ideas`, `chapters`, `critique`) with caching and regeneration.
- Distinguish cached vs fresh generation.
- Operate reliably under concurrent load and rate limits.

## 2) Goals and Non-Goals

### Goals
- Fast MVP with working search, metadata page, and generation.
- Strictly structured LLM output with schema validation.
- Persistence-first behavior to minimize duplicate LLM cost.
- Concurrency-safe generation flow.
- Basic observability (request IDs, structured logs, in-process metrics).
- Offline deterministic tests for backend and frontend logic.

### Non-Goals (for MVP)
- User accounts/auth.
- Multi-tenant architecture.
- Distributed cache/queue.
- Full production analytics stack (Prometheus/OpenTelemetry/etc.).
- Complex recommendation engine.

## 3) Current Architecture (Reference Design)

Monorepo:
- `backend/`: FastAPI + SQLModel + SQLite + OpenAI + Open Library integration.
- `frontend/bookwise/`: React + TypeScript + Vite app.
- `data/curated_books.yml`: curated title list.

Backend layering:
- Route -> Service -> Client -> DB
- No API key exposure to frontend.

Key backend modules:
- `app/main.py`: app setup, CORS, rate-limiter middleware, request ID middleware.
- `app/api/routes/*`: route handlers.
- `app/services/*`: orchestration/business logic.
- `app/clients/openlibrary.py`, `app/clients/openai_llm.py`: external integrations.
- `app/db/models.py`, `app/db/session.py`: persistence.
- `app/schemas/generation.py`: strict Pydantic output contracts.

## 4) Functional Scope

### 4.1 Search
- Endpoint: `GET /api/search?q=...&limit=...`
- Debounced frontend query.
- English-only filtering in backend.
- Normalized result shape for UI cards.

### 4.2 Curated Random
- Endpoint: `GET /api/curated/random`
- Picks from `data/curated_books.yml`.
- Returns canonical work ID when available.
- Lazy resolves missing `work_id` via Open Library and persists YAML atomically.

### 4.3 Book Metadata
- Endpoint: `GET /api/books/{work_id}`
- Validates `work_id` format.
- Resolves from Open Library and upserts canonical `books` row.
- Returns normalized metadata object.

### 4.4 Generation (Persistence-First)
- Endpoint: `POST /api/books/{work_id}/generate/{section}?force=false`
- Sections:
  - `overview`
  - `key_ideas`
  - `chapters`
  - `critique`
- Behavior:
  - Auto-persist book if missing.
  - Return cached generation when complete and `force=false`.
  - Generate and upsert when missing or `force=true`.
  - Strict schema validation before persist.
- Pending/status:
  - `POST` may return `202` pending with `retry_after_ms` and `Retry-After`.
  - Polling endpoint: `GET /api/books/{work_id}/generations/{section}/status`

### 4.5 Health and Metrics
- `GET /health`
- `GET /api/health`
- `GET /metrics` (in-process counters and timer aggregates)

## 5) Data Model

### `books`
- `id` (PK, Open Library Work ID string like `OL123W`)
- `title`
- `authors` (string persisted form)
- `first_publish_year` nullable int
- `cover_url` nullable
- `openlibrary_url`
- `created_at`, `updated_at`

### `book_generations`
- `id` (PK int)
- `book_id` (FK -> books.id, indexed)
- `section` (indexed)
- `status` (`pending` | `complete` | `failed`, indexed)
- `content_json` JSON nullable
- `provider`
- `model`
- `prompt_version`
- `schema_version`
- `started_at`, `finished_at`
- `error_code`, `error_message`
- `attempt_count`
- `created_at`, `updated_at`

Uniqueness:
- `(book_id, section, provider, model, prompt_version)`

## 6) LLM and Schema Contracts

Provider rules:
- OpenAI only.
- Model from config (`backend/config/llm.yml`), currently `gpt-5-mini`.

Structured output path:
- OpenAI Responses API with strict JSON schema mode.
- Parse response from structured `output_json` chunk first, fallback to first text chunk.
- Validate with Pydantic models before persistence.

Section schemas (`app/schemas/generation.py`):
- `OverviewOut`:
  - `overview: str`
  - `reading_time_minutes: int`
- `KeyIdeasOut`:
  - `key_ideas: list[str]` with bounds
- `ChaptersOut`:
  - `chapters: list[{title, summary}]` with bounds
- `CritiqueOut`:
  - `strengths`, `weaknesses`, `who_should_read` lists with bounds

Token caps by section (service-level):
- overview: 800
- key_ideas: 800
- chapters: 2200
- critique: 1000

## 7) Reliability and Concurrency

Single-flight generation pattern:
- Claim generation row as `pending` under unique key.
- Competing requests:
  - `complete` -> immediate cached response
  - `pending` -> `202` in progress
  - `failed` + `force=false` -> safe failure response
  - `force=true` -> guarded transition to pending

Status transitions:
- `pending -> complete` on validated success.
- `pending -> failed` with categorized error code on failure.

Error categories:
- `schema_validation`
- `openai_error`
- `timeout`
- `unexpected`

## 8) Observability Requirements

### Logging
- Structured JSON logs.
- Request IDs from middleware (`X-Request-ID` pass-through/generation).
- Generation logs include:
  - section, work_id, cache key
  - cache hit/miss decision
  - OpenAI latency
  - validation failures

### Safe diagnostics for LLM failures
- On empty output:
  - log shape summary only (types/counts, no full payload)
- On JSON decode failure:
  - log `finish_reason`, `output_length`, `output_tail` (last 200 chars)
  - never log keys/secrets/full prompt/full raw response

### Metrics
- Counters (cache hit/miss, status transitions, errors)
- Timers (generation total, OpenAI latency, DB upsert latency)

## 9) Frontend UX Requirements

### App shell
- Header with product title, theme toggle, admin button.
- Routes:
  - `/` landing
  - `/book/:workId`
  - `/admin`

### Landing page
- Quote banner.
- Debounced search box.
- Scrollable results container.
- Surprise Me CTA.

### Book detail page
- Metadata header:
  - cover, title, authors, description, tags
- Generated insights section cards:
  - overview (always expanded)
  - key ideas (collapsible)
  - chapters (collapsible)
  - critique (collapsible)
- Each section:
  - independent loading/error/retry state
  - stored/generated badge
  - regenerate button (`force=true`)

### Polling behavior (important)
- Do not hammer POST generate endpoint.
- Flow:
  1. initial POST
  2. if pending -> poll GET status with backoff
  3. on complete -> one final POST to fetch stored payload
- Use retry hints (`retry_after_ms`, `Retry-After`) and caps on attempts/duration.

## 10) Security and Privacy

- Backend-only access to `OPENAI_API_KEY`.
- CORS locked to configured frontend origin.
- No prompt leakage to frontend.
- No full sensitive payloads in logs.
- Minimal exposure in errors returned to client.

## 11) API Contracts (v2 baseline)

Public/API routes:
- `GET /health` -> `{"status":"ok"}`
- `GET /api/health` -> `{"status":"ok"}`
- `GET /api/search`
- `GET /api/curated/random`
- `GET /api/books/{work_id}`
- `POST /api/books/{work_id}/generate/{section}`
- `GET /api/books/{work_id}/generations/{section}/status`
- `GET /metrics`

Generation POST response shape:
- Success `200`:
  - `book_id, section, prompt_version, provider, model, stored, status, content`
- Pending `202`:
  - `stored=false, in_progress=true, retry_after_ms, status="pending", cache_key`
  - header `Retry-After`

Status GET response shape:
- missing `404`: `{"status":"missing"}`
- pending `200`: `{"status":"pending","in_progress":true,"retry_after_ms":...}` + `Retry-After`
- complete `200`: `{"status":"complete","stored":true,"updated_at":..., "retry_after_ms":null}`
- failed `200`: `{"status":"failed","error_code":"...", "retry_after_ms":null}`

## 12) Build Plan in Chunks (MVP-first)

### Chunk 0: Repo/bootstrap (day 0)
Deliver:
- backend app startup
- health endpoints
- CORS config
- DB session/init
Accept:
- service boots
- `/health` returns 200

### Chunk 1: Discovery MVP (day 1)
Deliver:
- Open Library search client
- `/api/search` with english filter
- landing page with debounced search and result cards
Accept:
- no network in tests (mock client)
- typing -> stable results

### Chunk 2: Metadata persistence (day 1-2)
Deliver:
- `/api/books/{work_id}`
- work/author resolution
- books upsert
- book header UI
Accept:
- repeated calls upsert one row
- invalid ID -> 422

### Chunk 3: Curated random (day 2)
Deliver:
- curated YAML service
- `/api/curated/random`
- lazy resolve for null IDs + atomic write
Accept:
- deterministic tests with monkeypatch
- strict vs non-strict fallback behavior

### Chunk 4: Core intelligence MVP (day 3-4)
Deliver:
- generation endpoint for 4 sections
- strict schema validation
- persistence-first caching
- force regenerate
Accept:
- first call generates, second call cached
- invalid model output -> 422 + failed status

### Chunk 5: Concurrency-safe single-flight (day 4)
Deliver:
- pending/complete/failed state machine
- claim/update winner logic
- status endpoint for polling
Accept:
- competing calls do not duplicate LLM call
- pending returns 202 with retry hints

### Chunk 6: Frontend generated insights (day 5)
Deliver:
- section cards on book detail
- regenerate button
- stored/generated badge
- status polling with backoff
Accept:
- no POST hammering
- per-section independent behavior

### Chunk 7: Observability baseline (day 5-6)
Deliver:
- request ID middleware
- structured logs
- metrics endpoint
- safe LLM failure diagnostics
Accept:
- logs include request_id and relevant generation fields
- no secret leakage

### Chunk 8: Hardening and release prep (day 6+)
Deliver:
- expanded tests (API + UI polling)
- CI checks
- docs and runbooks
Accept:
- deterministic offline tests
- reproducible local setup

## 13) Testing Strategy

Backend:
- pytest + TestClient
- monkeypatch all external clients
- assert DB persistence/state transitions
- validate status/polling semantics

Frontend:
- vitest + testing-library
- mock API modules
- fake timers for polling/backoff
- verify retry/regenerate/collapse flows

Required offline coverage:
- no real OpenAI/OpenLibrary calls in tests

## 14) Acceptance Criteria for v2

- User can search, pick book, and open detail page.
- Generation works for all 4 sections with schema-validated content.
- Cached generation is reused; force regenerates.
- Concurrent requests do not duplicate LLM calls.
- Pending status is pollable without rate-limit hammering.
- Logs/metrics provide enough signal to debug model output failures safely.
- End-to-end local dev setup works for backend + frontend.

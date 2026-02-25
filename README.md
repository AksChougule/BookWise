# BookWise

BookWise is a monorepo with:
- `backend`: FastAPI + SQLModel service for search, curated picks, book metadata, and LLM generation.
- `frontend`: React + Vite app for landing/search, book detail, and admin utilities.

## Repo Structure

```text
BookWise/
├── backend/
│   ├── app/
│   ├── config/
│   ├── pyproject.toml
│   └── .env
├── frontend/
│   └── bookwise/
├── data/
│   └── curated_books.yml
└── SPEC.md
```

## Requirements

- Python `3.12+`
- Poetry
- Node `>=20.19.0` (or `>=22.12.0`) for Vite 7

## Backend Quick Start

```bash
cd backend
poetry install
poetry run uvicorn app.main:app --reload
```

Backend runs on `http://localhost:8000` by default.

### Backend Tests

```bash
cd backend
poetry run pytest -q
```

## Frontend Quick Start

```bash
cd frontend/bookwise
npm install
npm run dev
```

Frontend runs on `http://localhost:5173` by default.

### Frontend Build/Test

```bash
cd frontend/bookwise
npm run build
npm run test
```

## Environment & Config

### Backend `.env` (in `backend/.env`)

Common variables:
- `OPENAI_API_KEY`: required for generation calls.
- `DATABASE_URL`: default SQLite path if omitted.
- `FRONTEND_ORIGIN`: CORS origin (default local Vite URL).
- `OPENLIBRARY_BASE_URL`: defaults to `https://openlibrary.org`.
- Optional LLM overrides:
  - `LLM_TEMPERATURE`
  - `LLM_MAX_OUTPUT_TOKENS`
  - `LLM_TIMEOUT_SECONDS`

### LLM YAML config

`backend/config/llm.yml` defaults:
- `provider: openai`
- `model: gpt-5-mini`
- `temperature: null`
- `max_output_tokens: 1200`
- `timeout_seconds: 45`

## API Overview

Health and admin:
- `GET /health`
- `GET /api/health`
- `GET /metrics`

Book/product endpoints:
- `GET /api/search?q=...&limit=...`
- `GET /api/curated/random`
- `GET /api/books/{work_id}`
- `POST /api/books/{work_id}/generate/{section}`
- `GET /api/books/{work_id}/generations/{section}/status`

Valid generation sections:
- `overview`
- `key_ideas`
- `chapters`
- `critique`

## Notes

- Generation is persistence-first: cached complete results are returned without re-calling OpenAI unless forced.
- Pending generation returns `202` and includes `retry_after_ms`; status polling is available via the GET status endpoint.
- Curated books are loaded from `data/curated_books.yml`.

## Troubleshooting

- Frontend blank page or dev server errors:
  - verify Node version is `>=20.19.0`.
- OpenAI key errors:
  - ensure `OPENAI_API_KEY` is set in `backend/.env`.
- Rate limiting (`429`) on generate:
  - use generation status polling endpoint instead of repeated POST retries.

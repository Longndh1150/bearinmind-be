# Bear In Mind — Backend & AI

API and AI layer for **Bear In Mind**: an LLM-assisted system that matches sales opportunities to internal engineering divisions at Rikkeisoft, syncs with **HubSpot**, and powers chat, matching, CRM workflows, and scheduled reminders.

## Overview

- **REST API** — FastAPI service consumed by the frontend (`bearinmind-fe`)
- **AI agents** — LangGraph / LangChain flows for opportunity matching, CRM sync, memory, multi-source queries, and notifications
- **Data** — PostgreSQL (relational), Redis (cache / Celery broker), ChromaDB (embeddings for unit capabilities and case studies)
- **Integrations** — HubSpot (deals), optional HRM / Salekit tools as the project wires them in

## Getting Started

```bash
# Python version
# - `pyproject.toml` requires Python >= 3.13
# - If you're using `pip + venv`, make sure your `python` points to 3.13+
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

pip install -r requirements.txt

copy .env.example .env   # Windows — or: cp .env.example .env
# Default `DATABASE_URL`: postgres@localhost:5432/bearinmind — update `.env` if yours differs.

# Infrastructure: Redis + Chroma (and optional Postgres container — omit `postgres` if you use local PG)
docker compose up -d redis chroma

# Database migrations
alembic upgrade head

# API (dev)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# Or FastAPI CLI
fastapi dev app/main.py
```

- **Recommended: use `uv` for env + dependencies (optional)**  
  Keep the default `venv + pip` flow above if you prefer. If you use `uv`, the typical workflow is:

```bash
# Create/refresh the environment from pyproject/uv.lock
uv sync

# Add a dependency (updates pyproject + lock)
uv add <package>

# Run commands inside the uv-managed environment
uv run ruff check .
uv run ruff format .
uv run pytest
uv run fastapi dev app/main.py

# Or run the one-shot local CI
uv run ci
```

- **Liveness:** `GET http://localhost:8000/health`
- **Readiness** (needs Docker up): `GET http://localhost:8000/api/v1/health/ready`
- **Tests:** `pytest` (default excludes integration). With stack running: `pytest -m integration`
- **Optional LLM smoke** (requires `LLM_API_KEY`): `python scripts/llm_smoke.py`

## Commands

| Command | Description |
|---------|-------------|
| `uvicorn app.main:app --reload` | Dev API server |
| `pytest` | Unit tests (excludes `@pytest.mark.integration` by default) |
| `pytest -m integration` | Full checks including DB/Redis/Chroma readiness |
| `pytest --cov=app --cov-report=term-missing` | Tests with coverage (terminal) |
| `pytest --cov=app --cov-report=html` | Coverage HTML report → `htmlcov/` |
| `ruff format .` | Format code |
| `ruff check .` | Lint |
| `ruff check . --fix` | Auto-fix safe issues |
| `python scripts/verify.py` | One-shot: format + lint + tests w/ coverage |
| `mypy app` | Static typing (if configured) |
| `docker compose up -d redis chroma` | Redis + Chroma (use local Postgres per `.env`; optional `postgres` service in compose) |
| `alembic upgrade head` | Apply migrations |
| `celery -A app.worker worker -l info` | Celery worker (when tasks exist) |
| `celery -A app.worker beat -l info` | Scheduled jobs (e.g. D.Lead reminders) |

## Stack

| | Tool |
|-|------|
| Language | Python 3.12+ |
| API | FastAPI |
| AI | LangChain / LangGraph, LLM via API (e.g. Claude / OpenAI) |
| DB | PostgreSQL + SQLAlchemy 2.x (or equivalent) + Alembic migrations |
| Vector | ChromaDB (or compatible) for embeddings / semantic search |
| Cache / queue | Redis |
| Background jobs | Celery + Celery Beat |
| HTTP client | `httpx` (async) for external APIs |
| CRM | HubSpot API (create/update deals) |

## Project structure

**Current (Phase 0+):**

```
app/
├── main.py
├── api/
│   ├── router.py
│   └── routes/
│       └── health.py
├── core/
│   └── config.py           # pydantic-settings
├── db/
│   ├── base.py
│   └── session.py
└── ai/
    └── graphs/
        └── smoke.py        # LangGraph scaffold
alembic/                    # migrations
scripts/
    └── llm_smoke.py        # optional OpenAI-compatible LLM smoke (OpenRouter supported)
```

**Target (later phases):** add `models/`, `schemas/`, `services/`, `ai/agents/`, `ai/tools/`, `workers/`, `integrations/` as in [`docs/design/architecture.md`](docs/design/architecture.md).

## User story ↔ backend surface (reference)

| Story | Focus | Typical endpoints / jobs |
|-------|--------|---------------------------|
| #1 | Chat + matching | `POST /chat` (or `/v1/chat`), matching agent + Chroma |
| #2 | Leader notifications | `GET /notifications`, match trigger → notification records |
| #3 | Division capabilities | `PUT /units/{id}/capabilities`, HRM / case-study tools |
| #4 | Memory + reminders | Memory agent, Celery beat, incremental updates |
| #5 | HubSpot sync | Opportunities CRUD, `push-crm`, HubSpot tools |
| #6 | Opportunity dashboard | `GET /opportunities` (filters; HubSpot + local unofficial) |

## Docs

- [`docs/project_overview.md`](docs/project_overview.md) — product context (English)
- [`docs/user_stories.md`](docs/user_stories.md) — six user stories (US1–US6) and acceptance criteria
- [`docs/design/architecture.md`](docs/design/architecture.md) — backend & AI architecture
- [`docs/design/system_requirements.md`](docs/design/system_requirements.md) — functional & non-functional requirements
- [`docs/design/implementation_plan.md`](docs/design/implementation_plan.md) — phased implementation plan
- [`CLAUDE.md`](CLAUDE.md) — AI assistant / developer guide for this repository

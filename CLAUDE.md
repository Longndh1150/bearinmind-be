# Bear In Mind — Backend & AI

## Project

LLM-powered **opportunity-to-division matching**, **CRM sync** (HubSpot), **unit capability memory**, **multi-source opportunity listing**, and **notifications / reminders** for Rikkeisoft’s Bear In Mind hackathon product.

## Architecture

### API + AI agents (single service, clear boundaries)

```
app/
├── main.py              # FastAPI app, middleware, exception handlers, CORS
├── api/                 # Versioned HTTP routers only (thin)
├── core/                # config (pydantic-settings), logging, deps, security
├── db/                  # engine, session, Alembic
├── models/              # SQLAlchemy models
├── schemas/             # Pydantic v2 models for API + agent I/O
├── services/            # Use-cases: orchestrate repos + agents (no LLM prompts here)
├── ai/
│   ├── agents/          # LangGraph graphs: matching, crm_sync, memory, query, notify
│   ├── tools/           # LangChain tools: HubSpot, DB, HRM, case study, vector search
│   ├── chains/          # Optional smaller chains shared by agents
│   └── prompts/         # Jinja or Python string templates; version consciously
├── workers/             # Celery: broker Redis, result backend optional
└── integrations/        # Thin clients for HubSpot / HRM HTTP APIs
```

### Agent responsibilities (map to user stories)

| Agent / area | User stories | Role |
|--------------|--------------|------|
| **Matching** | #1 | Parse opportunity text → entity extraction → vector retrieval (Chroma) → rank units → formatted explanation + contact |
| **CRM sync** | #5 | Extract opportunity from conversation → confirm → create/update HubSpot deal → persist local state |
| **Memory** | #3, #4 | Load prior unit context → incremental Q&A → persist + re-embed capabilities |
| **Opportunity query** | #6 | Merge local (unofficial) + HubSpot (official) → filtered list |
| **Notification** | #2 | On new/relevant opportunity → create leader-facing notifications |
| **Reminder** | #4 | Celery beat → prompt D.Lead with preloaded context |

### Data stores

- **PostgreSQL** — units, opportunities, conversations metadata, notifications, capability snapshots
- **Redis** — cache, Celery broker, optional pub/sub for real-time later
- **ChromaDB** — embeddings for unit capabilities and case studies; re-index when capabilities change

## Tech Stack

| Category | Tool |
|----------|------|
| Runtime | Python 3.12+ |
| API | FastAPI |
| Validation | Pydantic v2 |
| ORM | SQLAlchemy 2.x + Alembic |
| AI | LangChain + LangGraph; LLM via vendor API (Claude / GPT per config) |
| Vector | ChromaDB (embedded or client mode via Docker) |
| Async HTTP | `httpx` |
| Tasks | Celery + Redis; Celery Beat for schedules |
| CRM | HubSpot REST API |
| Auth | JWT (`python-jose`) + password hashing (Argon2) |

## Commands

```bash
# Install
pip install -r requirements.txt

# API (dev)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Tests
pytest

# Lint / format (when configured)
ruff check .
ruff format .

# Infra
docker compose up -d postgres redis chromadb

# Workers (when implemented)
celery -A app.workers.celery_app worker -l info
celery -A app.workers.celery_app beat -l info
```

## Key Conventions

### Configuration

- Use **pydantic-settings** with a single `Settings` class; load from `.env`
- Never commit secrets; document required keys in `.env.example` (HubSpot, LLM, DB URLs, Redis)

### API layer

- Routers in `api/` call **services**, not raw ORM or agents directly when the flow is non-trivial
- Use **dependency injection** (`Depends`) for DB sessions and settings
- Prefer **async** endpoints when using async DB drivers and `httpx`
- Version paths if the frontend will evolve: e.g. `/api/v1/...`

### Database

- **Alembic** for all schema changes; no ad-hoc DDL in application code
- Models use explicit `__tablename__` and indexes for foreign keys and query filters (opportunity status, source, unit)

### AI layer

- **LangGraph** (or subgraphs) per major workflow; keep graphs in `ai/agents/` with one module per agent
- **Tools** are small, testable functions wrapped with LangChain `tool`; side effects (HubSpot write) only after user confirmation in CRM sync flow
- **Prompts** live under `ai/prompts/`; avoid embedding huge strings inside route handlers
- Log **trace ids** or `conversation_id` / `opportunity_id` for observability

### External integrations

- **HubSpot**: rate limits and retries with backoff; map errors to HTTP 502/503 with safe messages
- **HRM / Salekit**: isolate behind integration modules; mock in tests

### Security

- Do not log API keys, tokens, or full PII from CRM payloads
- Validate HubSpot webhooks (if added later) with signatures
- **Auth**: Use JWT bearer tokens for frontend calls; store only `password_hash` (never raw password).
- **Password hashing**: Prefer **Argon2id** (`argon2-cffi`) for user passwords. Never implement custom crypto.

## Scaffolding added (Phase 0.5)

This repository now includes a minimal, production-shaped scaffold for authentication and user management:

- `app/schemas/`: Pydantic v2 models for API boundaries and LLM JSON parsing
  - `user.py`: `UserCreate`, `UserLogin`, `UserPublic`
  - `auth.py`: `Token`, `TokenPayload`
  - `llm.py`: example `OpportunityExtract` schema for parsing LLM JSON output
- `app/models/`: SQLAlchemy models
  - `user.py`: `User` table
- `app/services/`: business logic as **static classes**
  - `UserService`: create/authenticate users
  - `AuthService`: login → JWT token
- `app/core/security.py`: password hashing + JWT encode/decode helpers
- `app/api/routes/auth.py`: sample auth routes (`/api/v1/auth/register`, `/api/v1/auth/login`)

### Quick manual test

1. Run migrations:
   - `alembic upgrade head`
2. Start API:
   - `uvicorn app.main:app --reload`
3. Register:
   - `POST /api/v1/auth/register` with JSON `{ "email": "...", "password": "...", "full_name": "..." }`
4. Login:
   - `POST /api/v1/auth/login` with JSON `{ "email": "...", "password": "..." }` → returns JWT

### HTTP client

- Use **`httpx`** for outbound calls — async client shared via app lifespan where appropriate
- Do **not** use `requests` inside async request path if it blocks the event loop unnecessarily

## Rules

- **Thin routers, fat services, focused agents** — business rules and LLM orchestration stay out of `main.py` and minimal in routers
- **One Alembic revision per logical schema change**; review migrations in PRs
- **Re-embed Chroma** when unit capabilities change (transaction or task after successful `PUT` capabilities)
- **CRM writes** go through the CRM sync agent / service path that enforces confirmation and idempotency where possible
- **Celery tasks** must be idempotent when retried (e.g. reminder sends)
- Prefer **explicit Pydantic models** for all API and agent boundaries — avoid `dict` soup
- Match frontend expectations: error shape and status codes should be consistent and documented in OpenAPI (`/docs`)

## Docs (this repository)

- `docs/project_overview.md` — product context
- `docs/user_stories.md` — US1–US6 and acceptance criteria
- `docs/design/architecture.md` — components and data stores
- `docs/design/system_requirements.md` — FR/NFR
- `docs/design/implementation_plan.md` — phased delivery

# Bear In Mind — Backend System Requirements

Functional and non-functional requirements for **bearinmind-be** (API + AI + workers). Story IDs refer to [`../user_stories.md`](../user_stories.md).

---

## 1. Functional requirements

### FR-1 — Opportunity matching (US1)

- Accept natural-language opportunity descriptions via chat API.
- Extract structured hints: industry, scope, tech stack, budget/scale when present.
- Return ranked internal units with rationale and a designated **contact person**.
- Support multi-turn dialogue for clarification.

### FR-2 — Notifications (US2)

- Persist notifications when an opportunity matches a leader’s unit (or rule set).
- Expose list API for the frontend (polling acceptable for v1).
- Store fit level **High** or **Medium** and opportunity summary fields.

### FR-3 — Unit capabilities (US3)

- Allow authenticated updates to unit capability records: experts, tech stack, links to HRM/Salekit-derived data when integrated.
- Persist changes in PostgreSQL and refresh vector index for affected units.

### FR-4 — Memory and reminders (US4)

- Schedule periodic reminders (configurable interval, e.g. weekly) for D.Lead/S.Lead to confirm or update unit data.
- Include **preloaded** prior capability context in reminder payloads.
- Support incremental updates without full re-entry of all fields.

### FR-5 — Opportunity lifecycle and HubSpot (US5)

- Store opportunities from chat (including drafts / unofficial).
- Support user confirmation before CRM write.
- Create or update HubSpot deals via API; record `pushed_at`, `is_official` or equivalent source flags.
- Allow correction and re-push after edits.

### FR-6 — Unified opportunity list (US6)

- Return a combined view: opportunities from **PostgreSQL** (unofficial) and **HubSpot** (official).
- Support filtering by at least: status, source, unit (exact fields agreed with frontend).

### FR-7 — Integrations

- **HubSpot**: deal create/update; handle API errors gracefully.
- **HRM** / **Salekit** (phase as available): read-only tools for staffing and case studies; mockable for demo.

---

## 2. Non-functional requirements

### NFR-1 — Performance

- Chat matching path: target **&lt; 5 s** end-to-end for typical prompts under normal load (depends on LLM latency).
- Opportunity list: paginated responses; avoid unbounded HubSpot pulls.

### NFR-2 — Reliability

- Database migrations via Alembic; no breaking schema changes without migration.
- Celery tasks idempotent where retries occur.

### NFR-3 — Security

- No secrets in logs; redact tokens and PII where not required for debugging.
- Validate input on all mutating endpoints (Pydantic).

### NFR-4 — Maintainability

- OpenAPI (`/docs`) reflects deployed contract.
- Agents and tools isolated in `ai/` for testability.

### NFR-5 — Demo / hackathon scope

- Mock external systems when credentials are unavailable.
- Single-region deployment acceptable.

---

## 3. Technology constraints

| Area | Requirement |
|------|-------------|
| Runtime | Python 3.12+ |
| API | FastAPI |
| ORM / DB | SQLAlchemy 2.x + Alembic + PostgreSQL |
| AI | LangChain + LangGraph; LLM via vendor API |
| Vector | ChromaDB (or compatible) |
| Queue | Celery + Redis |
| HTTP client | `httpx` (async) for integrations |

---

## 4. Out of scope (backend, initial delivery)

- Full outcome-based learning loop from closed-won CRM data (future).
- Multi-tenant SaaS hardening beyond single-team demo.
- Webhook signature validation for HubSpot **unless** webhooks are added.

---

**Version**: 1.0  
**Date**: 2026-04-09

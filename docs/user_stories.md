# Bear In Mind — User Stories

This document defines **US1–US6** and acceptance criteria for the backend. Keep it in sync with product discussions and [`project_overview.md`](project_overview.md).

Numbering **US1–US6** matches the estimate sheet and backend routing in this repo.

---

## US1 — Chat + opportunity matching (CRITICAL)

**As a** Sales representative  
**I want to** ask the AI assistant about a project opportunity  
**So that** I can quickly identify the most suitable internal unit and resources for a proposal

### Acceptance criteria

- User can enter an opportunity description (e.g. D365, Japan market, …).
- AI returns:
  - List of suitable divisions / units
  - Match rationale (technology, case study relevance, …)
  - Contact person for the unit
- AI extracts relevant attributes when possible: industry, scope, technology stack, budget / scale
- Supports multi-turn clarification in chat

### Backend / AI notes

- Matching agent: entity extraction → vector retrieval (e.g. ChromaDB) → rank → explain.
- Typical API: `POST /chat` (or `/api/v1/chat`).

---

## US2 — Proactive opportunity hints for leaders

**As a** Delivery Leader  
**I want to** receive notifications from the AI when an opportunity fits my unit  
**So that** I can proactively consider joining the proposal

### Acceptance criteria

- Notifications delivered in-product (popup / chat / notification center — exact UX with frontend).
- Content includes:
  - Opportunity information
  - Fit level (**High** / **Medium**)
  - Suggested next actions (view detail / participate) — *to be refined in design*
- Backend may use **polling** (`GET /notifications`) or push later; real-time transport is a product decision.

---

## US3 — Division lead updates unit capabilities

**As a** D.Lead (division lead)  
**I want to** update capability information for my units  
**So that** the AI uses the latest data for matching

### Acceptance criteria

- Persist:
  - **Experts** (e.g. name + focus areas)
  - **Tech stack** the unit can deliver — manual entry + values from DB
  - **Resources** (availability, consult-capable people, …) — from **HRM** when integrated
  - **Case studies** (domain, tech stack, …) — from **Salekit** when integrated
- Responses can reference prior context (“based on what we had before …”).
- Changes feed the matching knowledge base and trigger re-embedding where applicable.

### Backend notes

- Typical API: `PUT /units/{id}/capabilities`
- Tools: HRM client, case-study client, DB + vector re-index

---

## US4 — Unit capability memory + periodic update reminders

**As the** AI system (supporting D.Lead / S.Lead workflows)  
**I want to** remind D.Lead / S.Lead to refresh unit information on a schedule  
**So that** data stays accurate for matching

### Acceptance criteria

- Scheduled messages (e.g. Celery Beat — weekly or as configured).
- **Preload** previous unit context in the reminder.
- Interaction supports **confirm** and **incremental update** (do not re-ask everything from scratch).

### Note on “learning”

- **Outcome-based learning** (whether a match led to a win) is a **future enhancement**, not required for the same acceptance bar as above. The execution doc prioritizes **structured memory + reminders** for capability data.

---

## US5 — Store opportunities and sync to HubSpot

**As a** Sales representative  
**I want** the AI to capture opportunity details from our conversation and help update HubSpot  
**So that** I avoid manual entry and keep records complete and accurate

### Acceptance criteria

- Capture and persist opportunity data from chat.
- Surface data back to the user for **confirmation**.
- Propose and execute **push to HubSpot** (create/update deal) after confirmation.
- Return operation result to the user; allow **editing** and re-sync.

### Backend notes

- Opportunity fields include e.g. `is_official`, `pushed_at`, `source`.
- APIs: `POST /opportunities`, `PUT /opportunities/{id}/push-crm` (exact paths may be versioned).

---

## US6 — Open opportunity list (multi-source)

**As a** Delivery Leader / Solution Leader  
**I want to** look up open opportunities in the system  
**So that** I see the full pipeline (official and unofficial) and can plan participation and staffing

### Acceptance criteria

- Query a consolidated opportunity list.
- Sources include:
  - **Official**: opportunities from HubSpot (already created there).
  - **Unofficial**: from Sales–AI conversations, not yet pushed to CRM.
- Filtering (status, source, unit, …) as agreed with frontend.

### Backend notes

- Agent or service merges **local DB** + **HubSpot API**.
- Typical API: `GET /opportunities` with query parameters.

---

## Suggested build priority (backend)

Order reflects dependencies and demo value; adjust per sprint.

| Order | US | Focus |
|-------|-----|--------|
| 1 | US1 | Matching + chat API — core value |
| 2 | US5 | Persistence + HubSpot — data closure |
| 3 | US6 | Aggregated list — visibility |
| 4 | US2 | Notifications + match triggers |
| 5 | US3 | Capabilities + integrations |
| 6 | US4 | Schedulers + reminder content |

---

**Version**: 1.1  
**Date**: 2026-04-09  
**Related docs**: [`design/system_requirements.md`](design/system_requirements.md), [`design/architecture.md`](design/architecture.md)

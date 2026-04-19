"""Dev/admin router — only active when app_env != 'production'.

Endpoints for inspecting and resetting local data stores (ChromaDB, etc.).
Useful during development and demo setup. Never enable in production.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.tools.vector_search import COLLECTION_NAME, _get_collection, get_chroma_client
from app.core.config import settings
from app.db.session import get_session
from app.integrations.hubspot_client import HubSpotAPIError
from app.schemas.user import UserCreate, UserPublic
from app.services import hubspot_service
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dev", tags=["dev"])


def _guard_non_production() -> None:
    if settings.app_env == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dev endpoints are disabled in production.",
        )


# ── Response schemas ──────────────────────────────────────────────────────────


class ChromaUnitItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    unit_id: str
    unit_name: str
    tech_stack: list[str] = Field(default_factory=list)
    case_study_titles: list[str] = Field(default_factory=list)
    contact_name: str | None = None
    document_preview: str = Field(description="First 200 chars of the embedded document.")


class ChromaCollectionInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    collection_name: str
    total_units: int
    units: list[ChromaUnitItem]


class DevActionResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    action: str
    affected: int
    message: str


class DevSmokeResult(BaseModel):
    """Minimal health check for external APIs (no secrets in response)."""

    model_config = ConfigDict(extra="ignore")

    ok: bool
    message: str
    detail: str | None = Field(
        default=None,
        description="Short diagnostic (e.g. model name, counts). Never includes API keys.",
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post(
    "/auth/register-superuser",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    summary="[DEV] Create superuser account",
    description="Development-only bootstrap endpoint to create a superuser with email/password.",
)
async def dev_register_superuser(
    payload: UserCreate,
    session: AsyncSession = Depends(get_session),
) -> UserPublic:
    _guard_non_production()
    existing = await UserService.get_by_email(session, str(payload.email).lower())
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = await UserService.create(session, payload, is_superuser=True)
    return UserPublic.model_validate(user, from_attributes=True)


@router.get(
    "/chroma/units",
    response_model=ChromaCollectionInfo,
    summary="[DEV] List all units in ChromaDB",
    description=(
        "Returns every document currently indexed in the unit_capabilities collection. "
        "Disabled in production."
    ),
)
def dev_list_chroma_units() -> ChromaCollectionInfo:
    _guard_non_production()
    try:
        collection = _get_collection()
        result = collection.get(include=["documents", "metadatas"])
    except Exception as exc:
        logger.exception("Chroma get failed")
        raise HTTPException(status_code=502, detail=f"ChromaDB error: {exc}") from exc

    ids: list[str] = result.get("ids") or []
    metadatas: list[dict] = result.get("metadatas") or []
    documents: list[str] = result.get("documents") or []

    units: list[ChromaUnitItem] = []
    for i, uid in enumerate(ids):
        meta = metadatas[i] if i < len(metadatas) else {}
        doc = documents[i] if i < len(documents) else ""

        raw_tech = meta.get("tech_stack", "")
        tech_stack = [t for t in raw_tech.split("|") if t] if raw_tech else []

        raw_cs = meta.get("case_study_titles", "")
        case_study_titles = [c for c in raw_cs.split("|") if c] if raw_cs else []

        units.append(
            ChromaUnitItem(
                unit_id=uid,
                unit_name=meta.get("unit_name", "Unknown"),
                tech_stack=tech_stack,
                case_study_titles=case_study_titles,
                contact_name=meta.get("contact_name") or None,
                document_preview=doc[:200],
            )
        )

    return ChromaCollectionInfo(
        collection_name=COLLECTION_NAME,
        total_units=len(units),
        units=units,
    )


@router.delete(
    "/chroma/units/{unit_id}",
    response_model=DevActionResult,
    summary="[DEV] Delete a single unit from ChromaDB",
    description="Removes one unit by its Chroma ID. Disabled in production.",
)
def dev_delete_chroma_unit(unit_id: str) -> DevActionResult:
    _guard_non_production()
    try:
        collection = _get_collection()
        # Check it exists first
        existing = collection.get(ids=[unit_id])
        if not existing["ids"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unit '{unit_id}' not found in ChromaDB.",
            )
        collection.delete(ids=[unit_id])
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Chroma delete failed")
        raise HTTPException(status_code=502, detail=f"ChromaDB error: {exc}") from exc

    return DevActionResult(
        action="delete_unit",
        affected=1,
        message=f"Unit '{unit_id}' deleted from ChromaDB.",
    )


@router.delete(
    "/chroma/units",
    response_model=DevActionResult,
    summary="[DEV] Reset ChromaDB — delete ALL units",
    description=(
        "Drops the entire unit_capabilities collection and recreates it empty. "
        "Run `python -m scripts.seed.units` again to repopulate. Disabled in production."
    ),
)
def dev_reset_chroma() -> DevActionResult:
    _guard_non_production()
    try:
        import chromadb as _chromadb

        client = get_chroma_client()
        # Count before deleting
        try:
            col = client.get_collection(COLLECTION_NAME)
            count = col.count()
        except Exception:
            count = 0
        # Delete and recreate
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass  # already gone
        _get_collection()
    except Exception as exc:
        logger.exception("Chroma reset failed")
        raise HTTPException(status_code=502, detail=f"ChromaDB error: {exc}") from exc

    return DevActionResult(
        action="reset_chroma",
        affected=count,
        message=f"Deleted {count} unit(s) from '{COLLECTION_NAME}'. Collection recreated empty.",
    )


@router.post(
    "/chroma/seed",
    response_model=DevActionResult,
    summary="[DEV] Seed unit data (Postgres + Chroma)",
    description=(
        "Runs the built-in unit seed flow (same as `python -m scripts.seed.units`). "
        "Upserts unit capability data into PostgreSQL and then re-indexes to Chroma. "
        "Disabled in production."
    ),
)
async def dev_seed_chroma() -> DevActionResult:
    _guard_non_production()
    try:
        from scripts.seed.units import SEED_UNITS, seed_units

        await seed_units()
    except Exception as exc:
        logger.exception("Unit seed failed")
        raise HTTPException(status_code=502, detail=f"Seed error: {exc}") from exc

    return DevActionResult(
        action="seed_chroma",
        affected=len(SEED_UNITS),
        message=f"Seeded {len(SEED_UNITS)} unit(s) into PostgreSQL and '{COLLECTION_NAME}' (upserted).",
    )


def _smoke_llm_sync() -> DevSmokeResult:
    """Blocking LLM ping (runs in a thread pool from async route)."""
    if not (settings.llm_api_key or "").strip():
        return DevSmokeResult(ok=False, message="LLM_API_KEY is not set or empty.", detail=None)

    kwargs: dict = {"api_key": settings.llm_api_key}
    if settings.llm_base_url:
        kwargs["base_url"] = settings.llm_base_url
    from app.core.llm_tracking import instrument_openai_client
    client = instrument_openai_client(OpenAI(**kwargs))
    try:
        resp = client.chat.completions.create(
            model=settings.llm_model_secondary,
            messages=[{"role": "user", "content": "Reply with exactly: ok"}],
            max_tokens=8,
            temperature=0,
        )
        text = (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        logger.warning("LLM smoke failed: %s", exc)
        return DevSmokeResult(ok=False, message="LLM request failed.", detail=str(exc)[:400])

    return DevSmokeResult(
        ok=True,
        message="LLM API key works.",
        detail=f"model={settings.llm_model_secondary!r}, reply={text!r}",
    )


@router.get(
    "/smoke/llm",
    response_model=DevSmokeResult,
    summary="[DEV] Smoke test LLM API key",
    description=(
        "Calls the configured OpenAI-compatible API with a one-token style prompt. "
        "Use to verify LLM_API_KEY and LLM_BASE_URL without going through chat. "
        "Disabled in production."
    ),
)
async def dev_smoke_llm() -> DevSmokeResult:
    _guard_non_production()
    return await asyncio.to_thread(_smoke_llm_sync)


def _smoke_embeddings_sync(model_override: str | None = None) -> DevSmokeResult:
    """Blocking Embeddings ping (runs in a thread pool from async route)."""
    if not (settings.llm_api_key or "").strip():
        return DevSmokeResult(ok=False, message="LLM_API_KEY is not set or empty.", detail=None)

    kwargs: dict = {"api_key": settings.llm_api_key}
    if settings.llm_base_url:
        kwargs["base_url"] = settings.llm_base_url
    from app.core.llm_tracking import instrument_openai_client
    client = instrument_openai_client(OpenAI(**kwargs))
    
    target_model = model_override or settings.llm_embedding_model
    
    try:
        resp = client.embeddings.create(
            model=target_model,
            input="Test embedding"
        )
        logger.debug("Embedding response: %s", resp)
        dim = len(resp.data[0].embedding)
    except Exception as exc:
        logger.warning("Embeddings smoke failed: %s", exc)
        return DevSmokeResult(ok=False, message="Embeddings request failed.", detail=str(exc)[:400])

    return DevSmokeResult(
        ok=True,
        message="Embeddings API works.",
        detail=f"model={target_model!r}, dim={dim}",
    )


@router.get(
    "/smoke/embeddings",
    response_model=DevSmokeResult,
    summary="[DEV] Smoke test Embeddings API",
    description=(
        "Calls the configured OpenAI-compatible API to generate embeddings. "
        "Use to verify LLM_API_KEY and LLM_BASE_URL support embeddings. "
        "Disabled in production."
    ),
)
async def dev_smoke_embeddings(model: str | None = None) -> DevSmokeResult:
    _guard_non_production()
    return await asyncio.to_thread(_smoke_embeddings_sync, model)


@router.get(
    "/smoke/hubspot",
    response_model=DevSmokeResult,
    summary="[DEV] Smoke test HubSpot API key",
    description=(
        "Calls HubSpot ``GET /settings/v3/users`` and returns user count. "
        "Use to verify HUBSPOT_API_KEY. Disabled in production."
    ),
)
async def dev_smoke_hubspot() -> DevSmokeResult:
    _guard_non_production()
    if not (settings.hubspot_api_key or "").strip():
        return DevSmokeResult(ok=False, message="HUBSPOT_API_KEY is not set or empty.", detail=None)
    try:
        users = await hubspot_service.fetch_users()
    except HubSpotAPIError as exc:
        logger.warning("HubSpot smoke failed: %s", exc)
        return DevSmokeResult(
            ok=False,
            message="HubSpot request failed (check key and scopes).",
            detail=str(exc)[:400],
        )
    except Exception as exc:
        logger.exception("HubSpot smoke unexpected error")
        return DevSmokeResult(ok=False, message="HubSpot request failed.", detail=str(exc)[:400])

    return DevSmokeResult(
        ok=True,
        message="HubSpot API key works.",
        detail=f"users_fetched={len(users)}",
    )

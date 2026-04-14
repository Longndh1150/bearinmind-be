"""Dev/admin router — only active when app_env != 'production'.

Endpoints for inspecting and resetting local data stores (ChromaDB, etc.).
Useful during development and demo setup. Never enable in production.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.ai.tools.vector_search import COLLECTION_NAME, _get_collection
from app.core.config import settings

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


# ── Endpoints ─────────────────────────────────────────────────────────────────


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
        "Run seed_units again to repopulate. Disabled in production."
    ),
)
def dev_reset_chroma() -> DevActionResult:
    _guard_non_production()
    try:
        import chromadb as _chromadb

        client = _chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
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
        client.create_collection(COLLECTION_NAME)
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
    summary="[DEV] Seed ChromaDB with sample units",
    description=(
        "Runs the built-in seed data (same as `python -m scripts.seed_units`). "
        "Uses stable UUIDs — safe to call multiple times (idempotent upsert). "
        "Disabled in production."
    ),
)
def dev_seed_chroma() -> DevActionResult:
    _guard_non_production()
    try:
        from app.ai.tools.vector_search import index_unit
        from scripts.seed_units import SEED_UNITS

        for unit in SEED_UNITS:
            index_unit(**unit)
    except Exception as exc:
        logger.exception("Chroma seed failed")
        raise HTTPException(status_code=502, detail=f"Seed error: {exc}") from exc

    return DevActionResult(
        action="seed_chroma",
        affected=len(SEED_UNITS),
        message=f"Seeded {len(SEED_UNITS)} unit(s) into '{COLLECTION_NAME}' (upserted).",
    )

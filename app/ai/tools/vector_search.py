"""Chroma vector search tool for unit capabilities + case studies.

Ported from BearInMind/app/vector_store.py; adapted to use bearinmind-be
settings (host/port from config) and returns typed results.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import chromadb
from chromadb.utils import embedding_functions

from app.core.config import settings

COLLECTION_NAME = "unit_capabilities"


def _get_collection() -> chromadb.Collection:
    client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
    ef = embedding_functions.DefaultEmbeddingFunction()
    return client.get_or_create_collection(name=COLLECTION_NAME, embedding_function=ef)


@dataclass
class VectorSearchResult:
    unit_id: str
    unit_name: str
    document: str
    metadata: dict = field(default_factory=dict)


def index_unit(
    *,
    unit_id: str,
    unit_name: str,
    tech_stack: list[str],
    case_studies: str,
    case_study_titles: list[str] | None = None,
    contact_name: str = "",
    contact_email: str = "",
    experts_json: str = "",
    case_studies_json: str = "",
) -> None:
    """Embed & upsert a unit's capability document into Chroma.

    Called after Unit is created/updated in Postgres.
    case_study_titles: short display titles for each case study (for FE cards).
    """
    document = (
        f"Unit: {unit_name}. "
        f"Tech: {', '.join(tech_stack)}. "
        f"Case Studies: {case_studies}"
    )
    metadata: dict[str, str | list] = {
        "unit_id": unit_id,
        "unit_name": unit_name,
        # Chroma stores lists as JSON strings — we join with | for easy split
        "tech_stack": "|".join(tech_stack),
        "case_study_titles": "|".join(case_study_titles or []),
    }
    if contact_name:
        metadata["contact_name"] = contact_name
    if contact_email:
        metadata["contact_email"] = contact_email
    if experts_json:
        metadata["experts_json"] = experts_json
    if case_studies_json:
        metadata["case_studies_json"] = case_studies_json

    collection = _get_collection()
    collection.upsert(documents=[document], metadatas=[metadata], ids=[unit_id])


def search_units(query: str, top_k: int = 3) -> list[VectorSearchResult]:
    """Query Chroma for the top-k most relevant units.

    Returns a flat list of VectorSearchResult instead of raw Chroma dicts
    so callers don't have to unpack nested lists.
    """
    collection = _get_collection()
    raw = collection.query(query_texts=[query], n_results=top_k)

    ids: list[str] = raw["ids"][0] if raw["ids"] else []
    metadatas: list[dict] = raw["metadatas"][0] if raw["metadatas"] else []
    documents: list[str] = raw["documents"][0] if raw["documents"] else []

    return [
        VectorSearchResult(
            unit_id=ids[i],
            unit_name=metadatas[i].get("unit_name", "Unknown"),
            document=documents[i],
            metadata=metadatas[i],
        )
        for i in range(len(ids))
    ]

def get_all_units() -> list[VectorSearchResult]:
    """Fetch all units from ChromaDB."""
    collection = _get_collection()
    raw = collection.get()

    ids: list[str] = raw.get("ids") or []
    metadatas: list[dict] = raw.get("metadatas") or [{}] * len(ids)
    documents: list[str] = raw.get("documents") or [""] * len(ids)

    return [
        VectorSearchResult(
            unit_id=ids[i],
            unit_name=metadatas[i].get("unit_name", "Unknown"),
            document=documents[i],
            metadata=metadatas[i],
        )
        for i in range(len(ids))
    ]

def get_unit_by_id(unit_id: str) -> VectorSearchResult | None:
    """Fetch a specific unit by ID from ChromaDB."""
    collection = _get_collection()
    raw = collection.get(ids=[unit_id])
    
    if not raw or not raw.get("ids"):
        return None

    metadatas: list[dict] = raw.get("metadatas") or [{}]
    documents: list[str] = raw.get("documents") or [""]
    
    return VectorSearchResult(
        unit_id=raw["ids"][0],
        unit_name=metadatas[0].get("unit_name", "Unknown"),
        document=documents[0],
        metadata=metadatas[0],
    )


"""Chroma vector search tool for unit capabilities + case studies.

Ported from BearInMind/app/vector_store.py; adapted to use bearinmind-be
settings (host/port from config) and returns typed results.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from openai import OpenAI

try:
    import chromadb
except Exception:  # pragma: no cover - exercised in runtime fallback
    chromadb = None  # type: ignore[assignment]

from app.core.config import settings

COLLECTION_NAME = "unit_capabilities"
logger = logging.getLogger(__name__)

# Safe in-memory fallback when Chroma is unavailable.
_memory_store: dict[str, dict[str, Any]] = {}


def get_chroma_client():
    if chromadb is None:
        raise RuntimeError("chromadb package is not available")

    mode = settings.chroma_mode.strip().lower()
    if mode == "persistent":
        persist_dir = Path(settings.chroma_persist_dir).expanduser().resolve()
        persist_dir.mkdir(parents=True, exist_ok=True)
        return chromadb.PersistentClient(path=str(persist_dir))
    else:
        return chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)


def _get_collection():
    client = get_chroma_client()

    class OpenRouterEmbeddingFunction:

        def __init__(self) -> None:
            from app.core.llm_tracking import instrument_openai_client
            self._client = instrument_openai_client(OpenAI(
                api_key=settings.llm_api_key or "no-key",
                base_url=settings.llm_base_url or None,
            ))
            self._model = settings.llm_embedding_model

        @staticmethod
        def name() -> str:
            return "openrouter-embedding"

        def get_config(self) -> dict[str, str]:
            return {"model": self._model}

        def __call__(self, input: list[str]) -> list[np.ndarray]:
            if not input:
                return []
            
            embeddings = []
            for text in input:
                resp = self._client.embeddings.create(
                    model=self._model,
                    input=text,  # OpenRouter requires single string per request
                )
                embeddings.append(np.array(resp.data[0].embedding))
            return embeddings
        embed_documents = __call__
        embed_query = __call__

    ef = OpenRouterEmbeddingFunction()
    return client.get_or_create_collection(name=COLLECTION_NAME, embedding_function=ef)


@dataclass
class VectorSearchResult:
    unit_id: str
    unit_name: str
    document: str
    metadata: dict = field(default_factory=dict)


def _fallback_upsert(unit_id: str, unit_name: str, document: str, metadata: dict[str, Any]) -> None:
    _memory_store[unit_id] = {
        "unit_name": unit_name,
        "document": document,
        "metadata": metadata,
    }


def _fallback_search(query: str, top_k: int) -> list[VectorSearchResult]:
    # Lightweight lexical retrieval: rank by token overlap then substring match.
    q_tokens = set(re.findall(r"[a-z0-9_]+", query.lower()))
    ranked: list[tuple[int, str, dict[str, Any]]] = []

    for unit_id, row in _memory_store.items():
        unit_name = str(row.get("unit_name", "Unknown"))
        document = str(row.get("document", ""))
        text = f"{unit_name} {document}".lower()
        d_tokens = set(re.findall(r"[a-z0-9_]+", text))

        overlap = len(q_tokens & d_tokens)
        substring_bonus = 2 if query.lower().strip() and query.lower().strip() in text else 0
        score = overlap + substring_bonus
        if score > 0:
            ranked.append((score, unit_id, row))

    ranked.sort(key=lambda x: x[0], reverse=True)
    return [
        VectorSearchResult(
            unit_id=unit_id,
            unit_name=str(row.get("unit_name", "Unknown")),
            document=str(row.get("document", "")),
            metadata=dict(row.get("metadata", {})),
        )
        for _, unit_id, row in ranked[:top_k]
    ]


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

    try:
        collection = _get_collection()
        collection.upsert(documents=[document], metadatas=[metadata], ids=[unit_id])
        return
    except Exception as exc:
        logger.warning("Chroma upsert failed, falling back to in-memory index: %s", exc)
        _fallback_upsert(unit_id=unit_id, unit_name=unit_name, document=document, metadata=metadata)


def search_units(query: str, top_k: int = 3) -> list[VectorSearchResult]:
    """Query Chroma for the top-k most relevant units.

    Returns a flat list of VectorSearchResult instead of raw Chroma dicts
    so callers don't have to unpack nested lists.
    """
    from datetime import UTC, datetime
    import logging
    logger = logging.getLogger(__name__)

    try:
        t0 = datetime.now(UTC)
        logger.info("vector_search: Getting collection...")
        collection = _get_collection()
        t1 = datetime.now(UTC)
        logger.info(f"vector_search: _get_collection took {(t1 - t0).total_seconds():.3f}s")
        
        logger.info("vector_search: collection.query()...")
        raw = collection.query(query_texts=[query], n_results=top_k)
        t2 = datetime.now(UTC)
        logger.info(f"vector_search: collection.query took {(t2 - t1).total_seconds():.3f}s")

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
    except Exception as exc:
        logger.warning("Chroma query failed, using in-memory fallback search: %s", exc)
        return _fallback_search(query=query, top_k=top_k)


def get_all_units() -> list[VectorSearchResult]:
    """Fetch all units from ChromaDB (fallbacks to in-memory cache)."""
    try:
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
    except Exception as exc:
        logger.warning("Chroma get_all_units failed, using in-memory fallback: %s", exc)
        return [
            VectorSearchResult(
                unit_id=unit_id,
                unit_name=str(row.get("unit_name", "Unknown")),
                document=str(row.get("document", "")),
                metadata=dict(row.get("metadata", {})),
            )
            for unit_id, row in _memory_store.items()
        ]


def get_unit_by_id(unit_id: str) -> VectorSearchResult | None:
    """Fetch a specific unit by ID from ChromaDB (fallback to in-memory)."""
    try:
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
    except Exception as exc:
        logger.warning("Chroma get_unit_by_id failed, using in-memory fallback: %s", exc)
        row = _memory_store.get(unit_id)
        if not row:
            return None
        return VectorSearchResult(
            unit_id=unit_id,
            unit_name=str(row.get("unit_name", "Unknown")),
            document=str(row.get("document", "")),
            metadata=dict(row.get("metadata", {})),
        )

"""US1 Matching Agent.

Ported from BearInMind/app/matching_agent.py.
Uses bearinmind-be LLM config (OpenAI-compatible: OpenRouter, Groq, OpenAI, …)
instead of a hard-coded Groq client.

Flow:
  1. extract_entities(message) → OpportunityExtract
  2. search_units(query)       → list[VectorSearchResult]
  3. score_and_rank(...)       → list[MatchedUnit] + list[TeamSuggestion]
"""

from __future__ import annotations

import json
import logging

from openai import OpenAI

from app.ai.prompts.matching import EXTRACT_ENTITIES_SYSTEM, SCORE_AND_RANK_SYSTEM
from app.ai.tools.vector_search import VectorSearchResult, search_units
from app.core.config import settings
from app.schemas.chat import MatchedUnit, MatchRationale, TeamSuggestion
from app.schemas.llm import OpportunityExtract

logger = logging.getLogger(__name__)


def _llm_client() -> OpenAI:
    """Build an OpenAI-compatible client from BE settings.

    Works with OpenAI, OpenRouter, Groq (set LLM_BASE_URL + LLM_API_KEY).
    """
    kwargs: dict = {"api_key": settings.llm_api_key or "no-key"}
    if settings.llm_base_url:
        kwargs["base_url"] = settings.llm_base_url
    return OpenAI(**kwargs)


def _chat_json(client: OpenAI, system: str, user: str = "") -> dict:
    """Call LLM in JSON mode and return parsed dict."""
    messages = [{"role": "system", "content": system}]
    if user:
        messages.append({"role": "user", "content": user})

    resp = client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content or "{}"
    return json.loads(raw)


# ── Step 1: entity extraction ──────────────────────────────────────────────────

def extract_entities(message: str) -> OpportunityExtract:
    client = _llm_client()
    try:
        data = _chat_json(client, EXTRACT_ENTITIES_SYSTEM, message)
        return OpportunityExtract(**data)
    except Exception:
        logger.exception("Entity extraction failed; returning empty extract")
        return OpportunityExtract()


# ── Step 2 + 3: vector search + LLM rank ──────────────────────────────────────

def _build_units_context(results: list[VectorSearchResult]) -> str:
    lines = [
        f"ID: {r.unit_id}, Name: {r.unit_name}, Info: {r.document}"
        for r in results
    ]
    return "\n".join(lines)


def score_and_rank(
    opportunity: OpportunityExtract,
    vector_results: list[VectorSearchResult],
) -> tuple[list[MatchedUnit], list[TeamSuggestion]]:
    """Return (matched_units, suggestions) for the chat response."""
    if not vector_results:
        return [], []

    client = _llm_client()
    units_context = _build_units_context(vector_results)
    system = SCORE_AND_RANK_SYSTEM.format(
        opportunity_json=opportunity.model_dump_json(),
        units_context=units_context,
    )

    try:
        data = _chat_json(client, system)
    except Exception:
        logger.exception("Score/rank LLM call failed; returning empty results")
        return [], []

    llm_results: list[dict] = data.get("results", [])

    # Build a lookup: unit_id → VectorSearchResult for metadata
    meta_by_id = {r.unit_id: r for r in vector_results}

    matched_units: list[MatchedUnit] = []
    suggestions: list[TeamSuggestion] = []

    for rank_idx, item in enumerate(llm_results):
        unit_id = item.get("unit_id", "")
        meta = meta_by_id.get(unit_id)
        unit_name = meta.unit_name if meta else "Unknown Unit"
        contact_name = (meta.metadata.get("contact_name") if meta else None) or "Contact"
        contact_email: str | None = meta.metadata.get("contact_email") if meta else None

        fit_level_raw: str = item.get("fit_level", "low")
        fit_level = fit_level_raw if fit_level_raw in ("high", "medium", "low") else "low"

        rationale_raw: dict = item.get("rationale", {})
        rationale = MatchRationale(
            summary=rationale_raw.get("summary", ""),
            confidence=float(rationale_raw.get("confidence", 0.5)),
            evidence=rationale_raw.get("evidence", []),
        )

        matched_units.append(
            MatchedUnit(
                unit_id=unit_id,  # type: ignore[arg-type]
                unit_name=unit_name,
                contact_name=contact_name,
                contact_email=contact_email,
                fit_level=fit_level,  # type: ignore[arg-type]
                rationale=rationale,
            )
        )

        # Map to FE-friendly TeamSuggestion
        match_level = "High" if fit_level == "high" else "Medium"
        tech_stack = list(meta.metadata.get("tech_stack", [])) if meta else []
        suggestions.append(
            TeamSuggestion(
                name=unit_name,
                match_level=match_level,  # type: ignore[arg-type]
                tech_stack=tech_stack,
                case_studies=[],
                contact=contact_name,
                suggestion_rank=f"Đề xuất {rank_idx + 1}",
                summary=rationale.summary,
                contact_short_name=contact_name.split()[0] if contact_name else None,
                capability_tags=[
                    {"label": t, "tone": "teal"} for t in tech_stack[:3]
                ],
                variant="primary" if rank_idx == 0 else "secondary",
            )
        )

    return matched_units, suggestions


# ── Main entry point ───────────────────────────────────────────────────────────

def run_matching(message: str) -> tuple[OpportunityExtract, list[MatchedUnit], list[TeamSuggestion]]:
    """Full US1 pipeline: extract → vector search → rank.

    Returns (extracted_opportunity, matched_units, suggestions).
    """
    extracted = extract_entities(message)
    query = " ".join(extracted.tech_stack + extracted.requirements)
    if not query.strip():
        query = message[:500]

    vector_results = search_units(query, top_k=3)
    matched_units, suggestions = score_and_rank(extracted, vector_results)
    return extracted, matched_units, suggestions

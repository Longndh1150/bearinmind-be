"""US1 Matching Agent.

Ported from BearInMind/app/matching_agent.py.
Uses bearinmind-be LLM config (OpenAI-compatible: OpenRouter, Groq, OpenAI, …)
instead of a hard-coded Groq client.

Flow (called after context_analyzer has already classified intent):
  1. extract_entities(message, language) → OpportunityExtract
  2. search_units(query)                → list[VectorSearchResult]
  3. score_and_rank(..., language)      → list[MatchedUnit] + list[TeamSuggestion]
  4. _build_answer(..., language)       → natural-language reply in correct language
"""

from __future__ import annotations

import json
import logging

from openai import OpenAI

from app.ai.prompts.matching import (
    EXTRACT_ENTITIES_SYSTEM,
    SCORE_AND_RANK_SYSTEM,
    language_instruction,
)
from app.ai.tools.vector_search import VectorSearchResult, search_units
from app.core.config import settings
from app.schemas.chat import MatchedUnit, MatchRationale, TeamSuggestion
from app.schemas.context import DetectedLanguage
from app.schemas.llm import OpportunityExtract

logger = logging.getLogger(__name__)

# Default language used when caller does not supply one
_DEFAULT_LANGUAGE = DetectedLanguage.vi


from app.core.llm_tracking import instrument_openai_client


def _llm_client() -> OpenAI:
    """Build an OpenAI-compatible client from BE settings.

    Works with OpenAI, OpenRouter, Groq (set LLM_BASE_URL + LLM_API_KEY).
    """
    kwargs: dict = {"api_key": settings.llm_api_key or "no-key"}
    if settings.llm_base_url:
        kwargs["base_url"] = settings.llm_base_url
    return instrument_openai_client(OpenAI(**kwargs))


def _chat_json(client: OpenAI, system: str, user: str = "") -> dict:
    """Call LLM in JSON mode and return parsed dict."""
    messages = [{"role": "system", "content": system}]
    if user:
        messages.append({"role": "user", "content": user})

    resp = client.chat.completions.create(
        model=settings.llm_model_primary,
        messages=messages,
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content or "{}"
    return json.loads(raw)


# ── Step 1: entity extraction ──────────────────────────────────────────────────


def extract_entities(
    message: str,
    language: DetectedLanguage = _DEFAULT_LANGUAGE,
) -> OpportunityExtract:
    """Extract structured opportunity attributes from the user message.

    language is injected into the prompt so the LLM writes free-text fields
    (title, notes, …) in the correct language.
    """
    client = _llm_client()
    system = EXTRACT_ENTITIES_SYSTEM.format(
        language_instruction=language_instruction(language),
    )
    try:
        data = _chat_json(client, system, message)
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
    language: DetectedLanguage = _DEFAULT_LANGUAGE,
) -> tuple[list[MatchedUnit], list[TeamSuggestion]]:
    """Return (matched_units, suggestions) for the chat response."""
    if not vector_results:
        return [], []

    client = _llm_client()
    units_context = _build_units_context(vector_results)
    system = SCORE_AND_RANK_SYSTEM.format(
        opportunity_json=opportunity.model_dump_json(),
        units_context=units_context,
        language_instruction=language_instruction(language),
    )

    try:
        data = _chat_json(client, system)
    except Exception:
        logger.exception("Score/rank LLM call failed; returning empty results")
        return [], []

    llm_results: list[dict] = data.get("results", [])

    # Authoritative lookup: unit_id → VectorSearchResult (IDs come from the system, not LLM)
    meta_by_id = {r.unit_id: r for r in vector_results}

    matched_units: list[MatchedUnit] = []
    suggestions: list[TeamSuggestion] = []

    for rank_idx, item in enumerate(llm_results):
        # Validate that the unit_id LLM echoed back is one we actually sent it.
        # If it's not, discard the item — LLM may not invent IDs.
        unit_id = item.get("unit_id", "")
        meta = meta_by_id.get(unit_id)
        if meta is None:
            logger.warning("LLM returned unknown unit_id %r — skipping", unit_id)
            continue

        # All authoritative fields come from our system (vector search metadata),
        # not from the LLM output.
        unit_name = meta.unit_name
        contact_name = meta.metadata.get("contact_name") or "Contact"
        contact_email: str | None = meta.metadata.get("contact_email") or None

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

        # tech_stack stored as pipe-separated string in Chroma metadata
        raw_tech = meta.metadata.get("tech_stack", "") if meta else ""
        tech_stack = [t for t in raw_tech.split("|") if t] if raw_tech else []

        # case_study_titles stored as pipe-separated string in Chroma metadata
        raw_cs = meta.metadata.get("case_study_titles", "") if meta else ""
        case_studies = [c for c in raw_cs.split("|") if c] if raw_cs else []

        suggestions.append(
            TeamSuggestion(
                name=unit_name,
                match_level=match_level,  # type: ignore[arg-type]
                tech_stack=tech_stack,
                case_studies=case_studies,
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


# ── Step 4: natural-language answer ───────────────────────────────────────────


def _build_answer(
    user_message: str,
    extracted: OpportunityExtract,
    matched_units: list[MatchedUnit],
    language: DetectedLanguage = _DEFAULT_LANGUAGE,
) -> str:
    """Ask the LLM to write a natural-language reply in the detected language."""
    count = len(matched_units)
    unit_names = ", ".join(u.unit_name for u in matched_units) if matched_units else "none"

    lang_names = {
        DetectedLanguage.vi: "Vietnamese",
        DetectedLanguage.en: "English",
        DetectedLanguage.ja: "Japanese",
        DetectedLanguage.other: "the same language as the user message",
    }
    lang_name = lang_names.get(language, "Vietnamese")

    system = (
        f"You are a helpful assistant summarising unit-matching results for a sales team. "
        f"Write a SHORT (1-3 sentence) friendly response in {lang_name}. "
        "Mention how many units were found and their names. "
        "Do not include JSON or markdown."
    )
    user_prompt = (
        f"User message: {user_message}\n"
        f"Matched {count} unit(s): {unit_names}.\n"
        f"Opportunity title: {extracted.title or 'not detected'}.\n"
        "Write the assistant reply:"
    )
    client = _llm_client()
    try:
        resp = client.chat.completions.create(
            model=settings.llm_model_primary,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        logger.warning("Answer generation failed; using fallback text")
        if count:
            return f"Found {count} matching unit(s): {unit_names}."
        return "No matching units found. Please provide more details about the technology and market."


# ── Main entry point ───────────────────────────────────────────────────────────


def run_matching(
    message: str,
    language: DetectedLanguage = _DEFAULT_LANGUAGE,
) -> tuple[OpportunityExtract, list[MatchedUnit], list[TeamSuggestion], str]:
    """Full US1 pipeline: extract → vector search → rank → answer.

    Args:
        message: The user's opportunity description.
        language: Detected language from context_analyzer (already known at this point).

    Returns:
        (extracted_opportunity, matched_units, suggestions, answer_text)
    """
    extracted = extract_entities(message, language=language)
    query = " ".join(extracted.tech_stack + extracted.requirements)
    if not query.strip():
        query = message[:500]

    vector_results = search_units(query, top_k=3)
    matched_units, suggestions = score_and_rank(extracted, vector_results, language=language)
    answer = _build_answer(message, extracted, matched_units, language=language)
    return extracted, matched_units, suggestions, answer

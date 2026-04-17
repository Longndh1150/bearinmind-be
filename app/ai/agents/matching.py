"""US1 Matching Agent.

Ported from BearInMind/app/matching_agent.py.
Uses bearinmind-be LLM config (OpenAI-compatible: OpenRouter, Groq, OpenAI, …)
instead of a hard-coded Groq client.

Flow (called after context_analyzer has already classified intent):
  1. extract_entities(message, language) → OpportunityExtract
  2. search_units(query)                → list[VectorSearchResult]
  3. score_and_rank(..., language)      → list[MatchedUnit] + list[MatchedExpert] + list[TeamSuggestion]
  4. _build_answer(..., language)       → natural-language reply in correct language
"""

from __future__ import annotations


import time
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
from app.schemas.chat import MatchedExpert, MatchedUnit, MatchRationale, TeamSuggestion
from app.schemas.context import DetectedLanguage
from app.schemas.llm import OpportunityExtract

logger = logging.getLogger(__name__)

# Default language used when caller does not supply one
_DEFAULT_LANGUAGE = DetectedLanguage.vi


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
    """Build context string for the LLM including unit info and experts."""
    lines: list[str] = []
    for r in results:
        # Base unit info
        line = f"ID: {r.unit_id}, Name: {r.unit_name}, Info: {r.document}"

        # Parse and include expert info from metadata
        experts_json_str = r.metadata.get("experts_json", "")
        if experts_json_str:
            try:
                experts = json.loads(experts_json_str)
                if experts:
                    expert_parts = []
                    for exp in experts:
                        name = exp.get("name", "")
                        focus = ", ".join(exp.get("focus_areas", []))
                        expert_parts.append(f"{name} ({focus})" if focus else name)
                    line += f" | Experts: {'; '.join(expert_parts)}"
            except (json.JSONDecodeError, TypeError):
                pass

        lines.append(line)
    return "\n".join(lines)


def _build_experts_lookup(results: list[VectorSearchResult]) -> dict[str, dict]:
    """Build a lookup: (unit_id, expert_name) → expert metadata from system data.

    Returns { unit_id: { expert_name_lower: { name, focus_areas, profile_url, unit_id, unit_name } } }
    """
    lookup: dict[str, dict] = {}
    for r in results:
        unit_experts: dict[str, dict] = {}
        experts_json_str = r.metadata.get("experts_json", "")
        if experts_json_str:
            try:
                experts = json.loads(experts_json_str)
                for exp in experts:
                    name = exp.get("name", "")
                    unit_experts[name.lower()] = {
                        "name": name,
                        "focus_areas": exp.get("focus_areas", []),
                        "profile_url": exp.get("profile_url"),
                        "unit_id": r.unit_id,
                        "unit_name": r.unit_name,
                    }
            except (json.JSONDecodeError, TypeError):
                pass
        lookup[r.unit_id] = unit_experts
    return lookup


def score_and_rank(
    opportunity: OpportunityExtract,
    vector_results: list[VectorSearchResult],
    language: DetectedLanguage = _DEFAULT_LANGUAGE,
) -> tuple[list[MatchedUnit], list[MatchedExpert], list[TeamSuggestion]]:
    """Return (matched_units, matched_experts, suggestions) for the chat response."""
    if not vector_results:
        return [], [], []

    client = _llm_client()
    units_context = _build_units_context(vector_results)
    system = SCORE_AND_RANK_SYSTEM.format(
        opportunity_json=opportunity.model_dump_json(),
        units_context=units_context,
        language_instruction=language_instruction(language),
    )

    try:
        data = _chat_json(client, system)
    except Exception as e:
        print(f"Score/rank LLM call failed: {e}; returning empty results")
        return [], [], []

    llm_results: list[dict] = data.get("results", [])

    # Authoritative lookup: unit_id → VectorSearchResult (IDs come from the system, not LLM)
    meta_by_id = {r.unit_id: r for r in vector_results}

    # Expert lookup for validation
    experts_lookup = _build_experts_lookup(vector_results)

    matched_units: list[MatchedUnit] = []
    all_matched_experts: list[MatchedExpert] = []
    suggestions: list[TeamSuggestion] = []
    
    for rank_idx, item in enumerate(llm_results):
        # Validate that the unit_id LLM echoed back is one we actually sent it.
        # If it's not, discard the item — LLM may not invent IDs.
        unit_id = item.get("unit_id", "")
        meta = meta_by_id.get(unit_id)
        if meta is None:
            print(f"LLM returned unknown unit_id {unit_id!r} — skipping")
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

        # ── Parse recommended experts for this unit ──
        unit_experts_lookup = experts_lookup.get(unit_id, {})
        unit_matched_experts: list[MatchedExpert] = []

        for exp_item in item.get("recommended_experts", []):
            exp_name_raw = exp_item.get("name", "")
            # Validate expert name against system data
            exp_sys = unit_experts_lookup.get(exp_name_raw.lower())
            if exp_sys is None:
                print(f"LLM recommended unknown expert {exp_name_raw!r} for unit {unit_id} — skipping")
                continue

            matched_expert = MatchedExpert(
                name=exp_sys["name"],  # authoritative name from system
                unit_id=unit_id,
                unit_name=unit_name,
                focus_areas=exp_sys["focus_areas"],  # authoritative from system
                fit_reason=exp_item.get("fit_reason", ""),
                evidence=exp_item.get("evidence", []),
                relevance_score=float(exp_item.get("relevance_score", 0.5)),
                profile_url=exp_sys.get("profile_url"),
            )
            unit_matched_experts.append(matched_expert)
            all_matched_experts.append(matched_expert)

        # ── Map to FE-friendly TeamSuggestion ──
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
                recommended_experts=unit_matched_experts,
            )
        )

    return matched_units, all_matched_experts, suggestions


# ── Step 4: natural-language answer ───────────────────────────────────────────


def _build_answer(
    user_message: str,
    extracted: OpportunityExtract,
    matched_units: list[MatchedUnit],
    matched_experts: list[MatchedExpert],
    language: DetectedLanguage = _DEFAULT_LANGUAGE,
) -> str:
    """Ask the LLM to write a natural-language reply in the detected language."""
    count = len(matched_units)
    unit_names = ", ".join(u.unit_name for u in matched_units) if matched_units else "none"

    # Build expert summary for the answer
    expert_count = len(matched_experts)
    if matched_experts:
        top_experts = matched_experts[:5]  # Show top 5 experts max
        expert_lines = []
        for exp in top_experts:
            areas = ", ".join(exp.focus_areas[:3]) if exp.focus_areas else ""
            expert_lines.append(f"{exp.name} ({exp.unit_name}) - {areas}")
        expert_summary = "; ".join(expert_lines)
    else:
        expert_summary = "none"

    lang_names = {
        DetectedLanguage.vi: "Vietnamese",
        DetectedLanguage.en: "English",
        DetectedLanguage.ja: "Japanese",
        DetectedLanguage.other: "the same language as the user message",
    }
    lang_name = lang_names.get(language, "Vietnamese")

    system = (
        f"You are a helpful assistant summarising unit-matching and expert-matching results for a sales team. "
        f"Write a SHORT (2-4 sentence) friendly response in {lang_name}. "
        "Mention how many units were found and their names. "
        "Also mention the top recommended experts and briefly why they fit. "
        "Do not include JSON or markdown."
    )
    user_prompt = (
        f"User message: {user_message}\n"
        f"Matched {count} unit(s): {unit_names}.\n"
        f"Recommended {expert_count} expert(s): {expert_summary}.\n"
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
            return f"Found {count} matching unit(s): {unit_names}. {expert_count} expert(s) recommended."
        return "No matching units found. Please provide more details about the technology and market."


# ── Main entry point ───────────────────────────────────────────────────────────


def run_matching(
    message: str,
    language: DetectedLanguage = _DEFAULT_LANGUAGE,
) -> tuple[OpportunityExtract, list[MatchedUnit], list[MatchedExpert], list[TeamSuggestion], str]:
    """Full US1 pipeline: extract → vector search → rank → answer.

    Args:
        message: The user's opportunity description.
        language: Detected language from context_analyzer (already known at this point).

    Returns:
        (extracted_opportunity, matched_units, matched_experts, suggestions, answer_text)
    """
    extracted = extract_entities(message, language=language)

    query = " ".join(extracted.tech_stack + extracted.requirements)
    if not query.strip():
        query = message[:500]

    vector_results = search_units(query, top_k=3)
    matched_units, matched_experts, suggestions = score_and_rank(
        extracted, vector_results, language=language,
    )
    answer = _build_answer(message, extracted, matched_units, matched_experts, language=language)
    return extracted, matched_units, matched_experts, suggestions, answer


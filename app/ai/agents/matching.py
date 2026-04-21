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

import json
import logging
import time
from typing import Literal

from langchain_openrouter import ChatOpenRouter
from pydantic import BaseModel, Field

from app.ai.constants import (
    LLM_MATCHING_SCORE_RANK_MAX_TOKENS,
)
from app.ai.prompts.matching import (
    extract_entities_prompt,
    language_instruction,
    score_and_rank_prompt,
)
from app.ai.tools.vector_search import VectorSearchResult
from app.core.config import settings
from app.core.llm_tracking import LLMTrackingContext
from app.schemas.chat import MatchedExpert, MatchedUnit, MatchRationale, TeamSuggestion
from app.schemas.context import DetectedLanguage
from app.schemas.llm import OpportunityExtract

logger = logging.getLogger(__name__)

# Default language used when caller does not supply one
_DEFAULT_LANGUAGE = DetectedLanguage.vi


def _llm_client(max_tokens: int | None = None) -> ChatOpenRouter:
    """Build an OpenRouter-compatible client from BE settings.
    """
    kwargs: dict = {"api_key": settings.llm_api_key or "no-key"}
    if settings.llm_base_url:
        kwargs["base_url"] = settings.llm_base_url
    if max_tokens:
        kwargs["max_tokens"] = max_tokens
    # instrumenting pure LangChain object with llm_tracking isn't easily monkeypatched like openrouter sdk
    # we leave it out here for now
    return ChatOpenRouter(**kwargs, model=settings.llm_model_primary, max_retries=1)


# ── Step 1: entity extraction ──────────────────────────────────────────────────


def extract_entities(
    message: str,
    language: DetectedLanguage = _DEFAULT_LANGUAGE,
) -> OpportunityExtract:
    """Extract structured opportunity attributes from the user message.

    language is injected into the prompt so the LLM writes free-text fields
    (title, notes, …) in the correct language.
    """
    client = _llm_client(max_tokens=LLM_MATCHING_SCORE_RANK_MAX_TOKENS)
    chain = extract_entities_prompt | client.with_structured_output(OpportunityExtract, include_raw=True)

    try:
        t0 = time.time()
        response = chain.invoke({
            "language_instruction": language_instruction(language),
            "message": message,
        })
        t1 = time.time()
        
        data: OpportunityExtract = response["parsed"]
        raw_msg = response["raw"]
        
        if hasattr(raw_msg, "usage_metadata"):
            LLMTrackingContext.log_call(
                operation_name="extract_entities",
                elapsed_s=t1 - t0,
                usage=LLMTrackingContext._extract_usage(raw_msg),
                model=getattr(raw_msg, "response_metadata", {}).get("model_name", settings.llm_model_primary),
            )
        
        # Fallback for null fields causing Pydantic ValidationError
        if data.tech_stack is None:
            data.tech_stack = []
        if data.requirements is None:
            data.requirements = []
            
        return data
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


class LLMRecommendedExpert(BaseModel):
    name: str = ""
    fit_reason: str = ""
    relevance_score: float = 0.5

class LLMRationale(BaseModel):
    summary: str = ""
    confidence: float = 0.5

class LLMRankItem(BaseModel):
    unit_id: str = ""
    fit_level: Literal["high", "medium", "low"] = "low"
    rationale: LLMRationale = Field(default_factory=LLMRationale)
    recommended_experts: list[LLMRecommendedExpert] = Field(default_factory=list)

class LLMScoreRankResult(BaseModel):
    results: list[LLMRankItem] = Field(default_factory=list)
    final_answer: str = Field(
        min_length=10,
        description="A friendly, natural-language conversational reply answering the user directly in the exact requested language, stating the summary of found units and recommended experts."
    )

def score_and_rank(
    opportunity: OpportunityExtract,
    vector_results: list[VectorSearchResult],
    language: DetectedLanguage = _DEFAULT_LANGUAGE,
) -> tuple[list[MatchedUnit], list[MatchedExpert], list[TeamSuggestion], str]:
    """Return (matched_units, matched_experts, suggestions, final_answer) for the chat response."""
    fallback_msg = {
        DetectedLanguage.vi: "Dựa trên yêu cầu của anh, hiện tại em chưa tìm thấy đơn vị hoặc chuyên gia phù hợp nào ạ. Gấu sẽ tiếp tục cập nhật thêm các đơn vị và chuyên gia vào hệ thống, mong anh thông cảm nhé!",
        DetectedLanguage.en: "Based on your request, we currently couldn't find any suitable units or experts. We will continue to update our system with more units and experts, thank you for your understanding!",
        DetectedLanguage.ja: "ご要望に基づき、現在のところ適切なユニットや専門家が見つかりませんでした。今後もシステムにより多くのユニットや専門家を追加していきますので、ご了承ください。",
    }
    if not vector_results:
        return [], [], [], fallback_msg.get(language, fallback_msg[DetectedLanguage.vi])

    client = _llm_client(max_tokens=LLM_MATCHING_SCORE_RANK_MAX_TOKENS)
    units_context = _build_units_context(vector_results)

    chain = score_and_rank_prompt | client.with_structured_output(LLMScoreRankResult, include_raw=True)

    try:
        t0 = time.time()
        response = chain.invoke({
            "opportunity_json": opportunity.model_dump_json(),
            "units_context": units_context,
            "language_instruction": language_instruction(language),
        })
        t1 = time.time()
    except Exception:
        logger.exception("Score/rank LLM call failed; returning empty results")
        return [], [], [], fallback_msg.get(language, fallback_msg[DetectedLanguage.vi])

    data: LLMScoreRankResult = response["parsed"]
    raw_msg = response["raw"]
    
    if hasattr(raw_msg, "usage_metadata"):
        LLMTrackingContext.log_call(
            operation_name="score_and_rank",
            elapsed_s=t1 - t0,
            usage=LLMTrackingContext._extract_usage(raw_msg),
            model=getattr(raw_msg, "response_metadata", {}).get("model_name", settings.llm_model_primary),
        )

    llm_results: list[LLMRankItem] = data.results
    final_answer = data.final_answer.strip()
    
    if not final_answer:
        lang_map = {
            DetectedLanguage.vi: "Dựa trên yêu cầu của anh, đây là một số gợi ý phù hợp:",
            DetectedLanguage.en: "Based on your request, here are some suitable recommendations:",
            DetectedLanguage.ja: "ご要望に基づき、いくつかの適切な提案を以下に示します："
        }
        final_answer = lang_map.get(language, lang_map[DetectedLanguage.vi])

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
        unit_id = item.unit_id
        meta = meta_by_id.get(unit_id)
        if meta is None:
            logger.warning("LLM returned unknown unit_id %r — skipping", unit_id)
            continue

        # All authoritative fields come from our system (vector search metadata),
        # not from the LLM output.
        unit_name = meta.unit_name
        contact_name = meta.metadata.get("contact_name") or "Contact"
        contact_email: str | None = meta.metadata.get("contact_email") or None

        fit_level = item.fit_level

        rationale = MatchRationale(
            summary=item.rationale.summary,
            confidence=item.rationale.confidence,
            evidence=[],
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

        for exp_item in item.recommended_experts:
            exp_name_raw = exp_item.name
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
                fit_reason=exp_item.fit_reason,
                evidence=[],
                relevance_score=float(exp_item.relevance_score),
                profile_url=exp_sys.get("profile_url"),
            )
            unit_matched_experts.append(matched_expert)
            all_matched_experts.append(matched_expert)

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
                recommended_experts=unit_matched_experts,
            )
        )

    return matched_units, all_matched_experts, suggestions, final_answer



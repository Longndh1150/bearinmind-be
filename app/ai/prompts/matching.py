"""Prompt templates for the US1 matching agent.

Language is injected at call time via language_instruction(lang) so the
context_analyzer's detected language is used consistently — no per-prompt
auto-detection.
"""

from __future__ import annotations

from app.schemas.context import DetectedLanguage

# ---------------------------------------------------------------------------
# language_instruction() — called at prompt-format time
# ---------------------------------------------------------------------------

_LANG_NAMES: dict[DetectedLanguage, str] = {
    DetectedLanguage.vi: "Vietnamese (Tiếng Việt)",
    DetectedLanguage.en: "English",
    DetectedLanguage.ja: "Japanese (日本語)",
    DetectedLanguage.other: "the same language as the user's message",
}


def language_instruction(lang: DetectedLanguage) -> str:
    """Return the language rule block to embed in any prompt."""
    lang_name = _LANG_NAMES.get(lang, "Vietnamese (Tiếng Việt)")
    return (
        f"IMPORTANT — Language rule:\n"
        f"- Write all free-text fields (titles, summaries, rationales, hints, labels) "
        f"in {lang_name}.\n"
        f"- Keep JSON field *names*, enum *values* (high/medium/low, etc.), and "
        f"technical terms (tech stack names, product names) in English.\n"
        f"- Do NOT mix languages within a single free-text field."
    )


# ---------------------------------------------------------------------------
# EXTRACT_ENTITIES_SYSTEM
# Usage: EXTRACT_ENTITIES_SYSTEM.format(language_instruction=language_instruction(lang))
# ---------------------------------------------------------------------------

from langchain_core.prompts import ChatPromptTemplate

EXTRACT_ENTITIES_SYSTEM = """\
You are an expert at analysing sales opportunity descriptions.
Extract key attributes from the user's message and return ONLY a valid structured
object matching the schema.

{language_instruction}
"""

extract_entities_prompt = ChatPromptTemplate.from_messages([
    ("system", EXTRACT_ENTITIES_SYSTEM),
    ("user", "{message}")
])


# ---------------------------------------------------------------------------
# SCORE_AND_RANK_SYSTEM
# Usage: SCORE_AND_RANK_SYSTEM.format(
#            opportunity_json=...,
#            units_context=...,
#            language_instruction=language_instruction(lang),
#        )
# ---------------------------------------------------------------------------

SCORE_AND_RANK_SYSTEM = """\
You are an expert at evaluating the fit between a sales opportunity and
internal delivery units, AND at identifying the best individual experts
(personnel) within each unit for the opportunity.

Opportunity:
{opportunity_json}

Candidate units (from vector search):
{units_context}

Evaluate each unit and its experts. Return ONLY a valid structured response matching the schema.

Rules:
- Order results from best to worst fit.
- Include only units that are at least a low fit.
- The "evidence" array should have 2-4 concrete reasons.
- The "unit_id" values MUST be copied exactly from the candidate list above. Do NOT invent new IDs.
- For "recommended_experts": recommend 1-3 experts per unit whose focus areas best match the opportunity requirements.
- Expert "name" MUST be copied exactly from the candidate list. Do NOT invent names.
- Expert "fit_reason" should be specific: mention the expert's skills and how they relate to the opportunity.
- Expert "evidence" should cite concrete focus areas or experience from the data.
- Expert "relevance_score" should reflect how closely the expert's skills match.

{language_instruction}
"""

score_and_rank_prompt = ChatPromptTemplate.from_messages([
    ("system", SCORE_AND_RANK_SYSTEM)
])

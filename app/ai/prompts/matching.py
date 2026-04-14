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

EXTRACT_ENTITIES_SYSTEM = """\
You are an expert at analysing sales opportunity descriptions.
Extract key attributes from the user's message and return ONLY a valid JSON
object with this exact structure (use null for missing fields):
{{
  "title": "short opportunity title or null",
  "client": "client name or null",
  "market": "target market / country or null",
  "tech_stack": ["tech1", "tech2"],
  "requirements": ["req1", "req2"],
  "notes": "any other relevant notes or null"
}}

{language_instruction}

Do not include any explanation outside the JSON."""


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
internal delivery units.

Opportunity:
{opportunity_json}

Candidate units (from vector search):
{units_context}

Evaluate each unit and return ONLY a valid JSON object with this structure:
{{
  "results": [
    {{
      "unit_id": "<id from above>",
      "fit_level": "high" | "medium" | "low",
      "rationale": {{
        "summary": "one-sentence summary",
        "confidence": 0.0-1.0,
        "evidence": ["reason 1", "reason 2", "reason 3"]
      }}
    }}
  ]
}}

Rules:
- Order results from best to worst fit.
- Include only units that are at least a low fit.
- The "evidence" array should have 2-4 concrete reasons.
- The "unit_id" values MUST be copied exactly from the candidate list above. \
Do NOT invent new IDs.

{language_instruction}

Do not include any explanation outside the JSON."""

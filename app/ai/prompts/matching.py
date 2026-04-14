"""Prompt templates for the US1 matching agent."""

EXTRACT_ENTITIES_SYSTEM = """\
You are an expert at analysing sales opportunity descriptions.
Extract key attributes from the user's message and return ONLY a valid JSON object
with this exact structure (use null for missing fields):
{
  "title": "short opportunity title or null",
  "client": "client name or null",
  "market": "target market / country or null",
  "tech_stack": ["tech1", "tech2"],
  "requirements": ["req1", "req2"],
  "notes": "any other relevant notes or null"
}
Do not include any explanation outside the JSON."""

SCORE_AND_RANK_SYSTEM = """\
You are an expert at evaluating the fit between a sales opportunity and internal delivery units.

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
        "evidence": ["reason 1", "reason 2"]
      }}
    }}
  ]
}}
Order results from best to worst fit. Include only units that are at least a low fit.
Do not include any explanation outside the JSON."""

"""Unit tests for US1 matching agent logic.

All tests mock the LLM + Chroma — no external services required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.ai.agents.matching import (
    _build_units_context,
    score_and_rank,
)
from app.ai.tools.vector_search import VectorSearchResult
from app.schemas.llm import OpportunityExtract

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def sample_vector_results() -> list[VectorSearchResult]:
    return [
        VectorSearchResult(
            unit_id="unit-001",
            unit_name="Rikkei D365 Division",
            document="Unit: Rikkei D365 Division. Tech: D365, Power Platform. Case Studies: Japan retail.",
            metadata={"unit_id": "unit-001", "unit_name": "Rikkei D365 Division", "contact_name": "ThangLB"},
        ),
        VectorSearchResult(
            unit_id="unit-002",
            unit_name="Rikkei AI & Data",
            document="Unit: Rikkei AI & Data. Tech: Python, LLM. Case Studies: Internal AI system.",
            metadata={"unit_id": "unit-002", "unit_name": "Rikkei AI & Data", "contact_name": "MinhLN"},
        ),
    ]


@pytest.fixture()
def sample_opportunity() -> OpportunityExtract:
    return OpportunityExtract(
        title="D365 CRM for Japan retail",
        client="RetailCo",
        market="Japan",
        tech_stack=["D365", "Power Platform"],
        requirements=["Senior consultant", "Japan experience"],
    )


# ── _build_units_context ──────────────────────────────────────────────────────

def test_build_units_context_format(sample_vector_results):
    ctx = _build_units_context(sample_vector_results)
    assert "unit-001" in ctx
    assert "Rikkei D365 Division" in ctx
    assert "unit-002" in ctx
    # Each result on its own line
    lines = ctx.strip().splitlines()
    assert len(lines) == 2


def test_build_units_context_empty():
    assert _build_units_context([]) == ""


# ── score_and_rank ────────────────────────────────────────────────────────────

def _make_llm_response(results: list[dict]) -> MagicMock:
    """Build a mock OpenAI-like response containing `results`."""
    import json
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = json.dumps({"results": results})
    return mock_resp


def test_score_and_rank_returns_empty_for_no_vector_results(sample_opportunity):
    matched, suggestions = score_and_rank(sample_opportunity, [])
    assert matched == []
    assert suggestions == []


def test_score_and_rank_maps_llm_output_correctly(sample_opportunity, sample_vector_results):
    llm_payload = [
        {
            "unit_id": "unit-001",
            "fit_level": "high",
            "rationale": {
                "summary": "Strong D365 match",
                "confidence": 0.9,
                "evidence": ["D365 expertise", "Japan experience"],
            },
        },
        {
            "unit_id": "unit-002",
            "fit_level": "medium",
            "rationale": {
                "summary": "Partial match on AI tooling",
                "confidence": 0.6,
                "evidence": ["Python team"],
            },
        },
    ]
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _make_llm_response(llm_payload)

    with patch("app.ai.agents.matching._llm_client", return_value=mock_client):
        matched, suggestions = score_and_rank(sample_opportunity, sample_vector_results)

    assert len(matched) == 2
    assert matched[0].unit_id == "unit-001"  # type: ignore[comparison-overlap]
    assert matched[0].fit_level == "high"
    assert matched[0].rationale.confidence == 0.9
    assert matched[0].contact_name == "ThangLB"

    assert len(suggestions) == 2
    assert suggestions[0].match_level == "High"
    assert suggestions[0].variant == "primary"
    assert suggestions[1].variant == "secondary"
    assert suggestions[0].suggestion_rank == "Đề xuất 1"


def test_score_and_rank_clamps_invalid_fit_level(sample_opportunity, sample_vector_results):
    llm_payload = [
        {
            "unit_id": "unit-001",
            "fit_level": "EXCELLENT",  # invalid value — should clamp to "low"
            "rationale": {"summary": "ok", "confidence": 0.5, "evidence": []},
        }
    ]
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _make_llm_response(llm_payload)

    with patch("app.ai.agents.matching._llm_client", return_value=mock_client):
        matched, _ = score_and_rank(sample_opportunity, sample_vector_results)

    assert matched[0].fit_level == "low"


def test_score_and_rank_handles_llm_exception(sample_opportunity, sample_vector_results):
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = RuntimeError("LLM down")

    with patch("app.ai.agents.matching._llm_client", return_value=mock_client):
        matched, suggestions = score_and_rank(sample_opportunity, sample_vector_results)

    assert matched == []
    assert suggestions == []


def test_score_and_rank_unknown_unit_id_is_discarded(sample_opportunity, sample_vector_results):
    """LLM hallucinated a unit_id not in vector results — item must be discarded, not trusted."""
    llm_payload = [
        {
            "unit_id": "unit-999",  # not in sample_vector_results — hallucinated by LLM
            "fit_level": "medium",
            "rationale": {"summary": "maybe", "confidence": 0.4, "evidence": []},
        }
    ]
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _make_llm_response(llm_payload)

    with patch("app.ai.agents.matching._llm_client", return_value=mock_client):
        matched, suggestions = score_and_rank(sample_opportunity, sample_vector_results)

    # Hallucinated IDs must be silently dropped — never trusted
    assert matched == []
    assert suggestions == []

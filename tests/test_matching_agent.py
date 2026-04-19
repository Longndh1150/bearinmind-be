from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.ai.agents.matching import (
    _build_units_context,
    score_and_rank,
    LLMScoreRankResult,
    LLMRankItem,
    LLMRationale,
)
from app.ai.tools.vector_search import VectorSearchResult
from app.schemas.llm import OpportunityExtract

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
            metadata={"unit_id": "unit-002", "unit_name": "Rikkei AI & Data", "contact_name": "HungDT"},
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

def test_build_units_context_format(sample_vector_results):
    ctx = _build_units_context(sample_vector_results)
    assert "unit-001" in ctx
    assert "Rikkei D365 Division" in ctx
    assert "unit-002" in ctx
    lines = ctx.strip().splitlines()
    assert len(lines) == 2

def test_build_units_context_empty():
    assert _build_units_context([]) == ""

def _make_match_client(results: list[dict]) -> MagicMock:
    items = []
    for r in results:
        rat = LLMRationale(**r.get("rationale", {}))
        items.append(LLMRankItem(unit_id=r["unit_id"], fit_level=r["fit_level"], rationale=rat))
    
    res = LLMScoreRankResult(results=items)
    mock_runnable = MagicMock()
    mock_runnable.return_value = res
    mock_runnable.invoke.return_value = res
    client = MagicMock()
    client.with_structured_output.return_value = mock_runnable
    return client

def test_score_and_rank_returns_empty_for_no_vector_results(sample_opportunity):
    matched, experts, suggestions, final_answer = score_and_rank(sample_opportunity, [])
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
    with patch("app.ai.agents.matching._llm_client", return_value=_make_match_client(llm_payload)):
        matched, experts, suggestions, final_answer = score_and_rank(sample_opportunity, sample_vector_results)

    assert len(matched) == 2
    assert matched[0].unit_id == "unit-001"
    assert matched[0].fit_level == "high"
    assert matched[0].rationale.confidence == 0.9
    assert matched[0].contact_name == "ThangLB"

    assert len(suggestions) == 2
    assert suggestions[0].match_level == "High"
    assert suggestions[0].variant == "primary"
    assert suggestions[1].variant == "secondary"

def test_score_and_rank_handles_llm_exception(sample_opportunity, sample_vector_results):
    mock_runnable = MagicMock()
    mock_runnable.invoke.side_effect = RuntimeError("LLM down")
    client = MagicMock()
    client.with_structured_output.return_value = mock_runnable

    with patch("app.ai.agents.matching._llm_client", return_value=client):
        matched, experts, suggestions, final_answer = score_and_rank(sample_opportunity, sample_vector_results)

    assert matched == []
    assert suggestions == []

def test_score_and_rank_unknown_unit_id_is_discarded(sample_opportunity, sample_vector_results):
    llm_payload = [
        {
            "unit_id": "unit-999",
            "fit_level": "medium",
            "rationale": {"summary": "maybe", "confidence": 0.4, "evidence": []},
        }
    ]
    with patch("app.ai.agents.matching._llm_client", return_value=_make_match_client(llm_payload)):
        matched, experts, suggestions, final_answer = score_and_rank(sample_opportunity, sample_vector_results)

    assert matched == []
    assert suggestions == []

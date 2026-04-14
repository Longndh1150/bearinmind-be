"""Unit tests for the vector_search tool.

Mocks ChromaDB — no Chroma server required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.ai.tools.vector_search import VectorSearchResult, index_unit, search_units


def _mock_collection() -> MagicMock:
    col = MagicMock()
    col.query.return_value = {
        "ids": [["unit-001", "unit-002"]],
        "metadatas": [
            [
                {"unit_id": "unit-001", "unit_name": "D365 Division"},
                {"unit_id": "unit-002", "unit_name": "AI Division"},
            ]
        ],
        "documents": [
            [
                "Unit: D365 Division. Tech: D365. Case Studies: Japan retail.",
                "Unit: AI Division. Tech: Python. Case Studies: Internal AI.",
            ]
        ],
    }
    return col


# ── search_units ──────────────────────────────────────────────────────────────

def test_search_units_returns_typed_results():
    with patch("app.ai.tools.vector_search._get_collection", return_value=_mock_collection()):
        results = search_units("D365 Japan", top_k=2)

    assert len(results) == 2
    assert all(isinstance(r, VectorSearchResult) for r in results)
    assert results[0].unit_id == "unit-001"
    assert results[0].unit_name == "D365 Division"
    assert "D365" in results[0].document


def test_search_units_empty_chroma_response():
    mock_col = MagicMock()
    mock_col.query.return_value = {"ids": [[]], "metadatas": [[]], "documents": [[]]}

    with patch("app.ai.tools.vector_search._get_collection", return_value=mock_col):
        results = search_units("anything")

    assert results == []


def test_search_units_passes_top_k():
    mock_col = _mock_collection()
    with patch("app.ai.tools.vector_search._get_collection", return_value=mock_col):
        search_units("query", top_k=5)

    mock_col.query.assert_called_once_with(query_texts=["query"], n_results=5)


# ── index_unit ────────────────────────────────────────────────────────────────

def test_index_unit_builds_correct_document():
    mock_col = MagicMock()
    with patch("app.ai.tools.vector_search._get_collection", return_value=mock_col):
        index_unit(
            unit_id="unit-001",
            unit_name="D365 Division",
            tech_stack=["D365", "Power Platform"],
            case_studies="Japan retail rollout",
            contact_name="ThangLB",
        )

    call_kwargs = mock_col.upsert.call_args
    doc = call_kwargs.kwargs["documents"][0]
    assert "D365 Division" in doc
    assert "D365, Power Platform" in doc
    assert "Japan retail rollout" in doc


def test_index_unit_includes_contact_in_metadata():
    mock_col = MagicMock()
    with patch("app.ai.tools.vector_search._get_collection", return_value=mock_col):
        index_unit(unit_id="u1", unit_name="UnitA", tech_stack=[], case_studies="cs", contact_name="Alice")

    meta = mock_col.upsert.call_args.kwargs["metadatas"][0]
    assert meta["contact_name"] == "Alice"


def test_index_unit_omits_contact_when_empty():
    mock_col = MagicMock()
    with patch("app.ai.tools.vector_search._get_collection", return_value=mock_col):
        index_unit(unit_id="u1", unit_name="UnitA", tech_stack=[], case_studies="cs")

    meta = mock_col.upsert.call_args.kwargs["metadatas"][0]
    assert "contact_name" not in meta


def test_index_unit_uses_upsert_not_add():
    """Must use upsert so re-seeding doesn't duplicate."""
    mock_col = MagicMock()
    with patch("app.ai.tools.vector_search._get_collection", return_value=mock_col):
        index_unit(unit_id="u1", unit_name="UnitA", tech_stack=[], case_studies="cs")

    mock_col.upsert.assert_called_once()
    mock_col.add.assert_not_called()

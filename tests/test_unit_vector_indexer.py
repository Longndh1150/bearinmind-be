from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock, patch

import pytest

from app.services.unit_vector_indexer import reindex_unit


@pytest.mark.asyncio
async def test_reindex_unit_skips_when_not_found():
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)

    with patch("app.services.unit_vector_indexer.index_unit") as mock_index:
        await reindex_unit(str(uuid4()), session=session)

    mock_index.assert_not_called()


@pytest.mark.asyncio
async def test_reindex_unit_builds_payload_and_indexes():
    unit_id = uuid4()
    unit = SimpleNamespace(
        id=unit_id,
        name="AI Platform & Applied GenAI",
        tech_stack=["Python", "RAG"],
        notes="Owns AI copilots and retrieval systems.",
        contact_name="HieuNN",
        contact_email="hieunn@rikkeisoft.com",
        experts=[],
        case_studies=[
            SimpleNamespace(
                title="Matching Copilot",
                domain="Sales Enablement",
                tech_stack=["Python", "LangChain"],
                description="Match opportunities to internal units.",
            ),
            SimpleNamespace(
                title="Contract Assistant",
                domain="Legal Tech",
                tech_stack=["RAG", "LLM"],
                description="Risk analysis with citation.",
            ),
        ],
    )

    session = AsyncMock()
    session.get = AsyncMock(return_value=unit)

    with patch("app.services.unit_vector_indexer.index_unit") as mock_index:
        await reindex_unit(str(unit_id), session=session)

    mock_index.assert_called_once()
    kwargs = mock_index.call_args.kwargs
    assert kwargs["unit_id"] == str(unit_id)
    assert kwargs["unit_name"] == "AI Platform & Applied GenAI"
    assert kwargs["tech_stack"] == ["Python", "RAG"]
    assert kwargs["contact_name"] == "HieuNN"
    assert kwargs["contact_email"] == "hieunn@rikkeisoft.com"
    assert kwargs["case_study_titles"] == ["Matching Copilot", "Contract Assistant"]
    assert "domain=Sales Enablement" in kwargs["case_studies"]
    assert "Unit notes: Owns AI copilots and retrieval systems." in kwargs["case_studies"]

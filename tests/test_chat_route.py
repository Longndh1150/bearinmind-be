"""Unit tests for POST /api/v1/chat.

Tests run without a DB or LLM key — stubs out auth dep + matching agent.
"""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User
from app.schemas.chat import MatchedUnit, MatchRationale, TeamSuggestion
from app.schemas.llm import OpportunityExtract

# ── helpers ───────────────────────────────────────────────────────────────────

_FAKE_USER = User(
    id=uuid4(),
    email="test@rikkei.com",
    full_name="Test User",
    password_hash="x",
    is_active=True,
    is_superuser=False,
)

_FAKE_MATCHED = [
    MatchedUnit(
        unit_id="unit-d365",
        unit_name="D365 Division",
        contact_name="ThangLB",
        fit_level="high",
        rationale=MatchRationale(summary="Strong match", confidence=0.9, evidence=["D365"]),
    )
]
_FAKE_SUGGESTIONS = [
    TeamSuggestion(
        name="D365 Division",
        match_level="High",
        tech_stack=["D365"],
        case_studies=[],
        contact="ThangLB",
    )
]


def _auth_override():
    return _FAKE_USER


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def client_no_key():
    """TestClient where LLM_API_KEY is empty → stub path."""
    from app.api.deps import require_active_user
    app.dependency_overrides[require_active_user] = _auth_override
    with patch("app.api.routes.chat.settings") as mock_settings:
        mock_settings.llm_api_key = ""
        yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def client_with_agent():
    """TestClient where run_matching is mocked → real route logic, no LLM."""
    from app.api.deps import require_active_user
    app.dependency_overrides[require_active_user] = _auth_override
    yield TestClient(app)
    app.dependency_overrides.clear()


# ── tests ─────────────────────────────────────────────────────────────────────

def test_chat_stub_response_when_no_llm_key(client_no_key):
    r = client_no_key.post("/api/v1/chat", json={"message": "D365 Japan retail"})
    assert r.status_code == 200
    body = r.json()
    assert "conversation_id" in body
    assert body["answer"]
    assert isinstance(body["matched_units"], list)
    assert body["analysis_card"] is not None


def test_chat_requires_auth():
    c = TestClient(app, raise_server_exceptions=False)
    r = c.post("/api/v1/chat", json={"message": "hello"})
    assert r.status_code == 401


def test_chat_reuses_conversation_id(client_no_key):
    fixed_id = str(uuid4())
    r = client_no_key.post("/api/v1/chat", json={"message": "test", "conversation_id": fixed_id})
    assert r.status_code == 200
    assert r.json()["conversation_id"] == fixed_id


def test_chat_with_mocked_agent(client_with_agent):
    extract = OpportunityExtract(title="D365 Japan", market="Japan", tech_stack=["D365"])
    with patch(
        "app.api.routes.chat.run_matching",
        return_value=(extract, _FAKE_MATCHED, _FAKE_SUGGESTIONS),
    ), patch("app.api.routes.chat.settings") as ms:
        ms.llm_api_key = "fake-key"
        r = client_with_agent.post("/api/v1/chat", json={"message": "D365 Japan retail"})

    assert r.status_code == 200
    body = r.json()
    assert len(body["matched_units"]) == 1
    assert body["matched_units"][0]["unit_name"] == "D365 Division"
    assert body["matched_units"][0]["fit_level"] == "high"
    assert len(body["suggestions"]) == 1
    assert body["suggestions"][0]["match_level"] == "High"
    assert body["analysis_card"]["footer_hint"] is not None


def test_chat_agent_exception_falls_back_to_stub(client_with_agent):
    with patch(
        "app.api.routes.chat.run_matching",
        side_effect=RuntimeError("agent crashed"),
    ), patch("app.api.routes.chat.settings") as ms:
        ms.llm_api_key = "fake-key"
        r = client_with_agent.post("/api/v1/chat", json={"message": "anything"})

    assert r.status_code == 200
    # Should fall back to stub, not 500
    body = r.json()
    assert "conversation_id" in body


def test_chat_empty_message_rejected(client_no_key):
    r = client_no_key.post("/api/v1/chat", json={"message": ""})
    assert r.status_code == 422


def test_chat_response_shape(client_no_key):
    r = client_no_key.post("/api/v1/chat", json={"message": "some opportunity"})
    body = r.json()
    required_keys = {"conversation_id", "answer", "matched_units", "suggestions", "analysis_card", "suggested_actions"}
    assert required_keys.issubset(body.keys())

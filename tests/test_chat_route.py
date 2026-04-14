"""Unit tests for POST /api/v1/chat — intent-aware routing.

Tests run without a DB or LLM key — stubs out auth dep + DB session +
analyze_context + matching agent.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User
from app.schemas.chat import MatchedUnit, MatchRationale, TeamSuggestion
from app.schemas.context import (
    ChatIntent,
    ConversationContext,
    DetectedLanguage,
)
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

_FAKE_CONV_ID = uuid4()

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

_NOW = datetime(2026, 4, 14, 0, 0, 0, tzinfo=UTC)


def _make_context(intent: ChatIntent = ChatIntent.find_units, lang: DetectedLanguage = DetectedLanguage.vi) -> ConversationContext:
    return ConversationContext(
        intent=intent,
        language=lang,
        confidence=0.95,
        opportunity_hint="D365 Japan project" if intent == ChatIntent.find_units else None,
        clarification_needed="Bạn muốn tìm gì?" if intent == ChatIntent.clarify else None,
        raw_message="test message",
    )


def _auth_override():
    return _FAKE_USER


def _make_fake_conv(conv_id=None):
    from app.models.conversation import Conversation

    cid = conv_id or _FAKE_CONV_ID
    fake_conv = Conversation(user_id=_FAKE_USER.id)
    fake_conv.id = cid
    fake_conv.title = None
    fake_conv.created_at = _NOW
    fake_conv.updated_at = _NOW
    fake_conv.session_meta = None
    return fake_conv


def _make_fake_session(conv_id=None):
    """Return an AsyncMock that behaves like a DB session for chat tests."""
    fake_conv = _make_fake_conv(conv_id)

    session = AsyncMock()
    session.get = AsyncMock(return_value=fake_conv)

    async def _flush():
        pass

    session.flush = AsyncMock(side_effect=_flush)
    session.commit = AsyncMock()

    async def _refresh(obj):
        if not getattr(obj, "id", None):
            obj.id = uuid4()
        if not getattr(obj, "created_at", None):
            obj.created_at = _NOW
        if not getattr(obj, "updated_at", None):
            obj.updated_at = _NOW

    session.refresh = AsyncMock(side_effect=_refresh)
    session.add = MagicMock()

    fake_result = MagicMock()
    fake_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=fake_result)

    return session


def _session_override(conv_id=None):
    async def _get():
        yield _make_fake_session(conv_id)

    return _get


# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def client_no_key():
    """LLM_API_KEY empty → stub path, DB mocked."""
    from app.api.deps import get_session, require_active_user

    app.dependency_overrides[require_active_user] = _auth_override
    app.dependency_overrides[get_session] = _session_override()
    with patch("app.api.routes.chat.settings") as mock_settings:
        mock_settings.llm_api_key = ""
        yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def client_with_context(intent: ChatIntent = ChatIntent.find_units):
    """analyze_context mocked → real route logic, no LLM, DB mocked."""
    from app.api.deps import get_session, require_active_user

    app.dependency_overrides[require_active_user] = _auth_override
    app.dependency_overrides[get_session] = _session_override()
    yield TestClient(app)
    app.dependency_overrides.clear()


# ── stub path tests ────────────────────────────────────────────────────────────


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
    fixed_id = str(_FAKE_CONV_ID)
    r = client_no_key.post("/api/v1/chat", json={"message": "test", "conversation_id": fixed_id})
    assert r.status_code == 200
    assert r.json()["conversation_id"] == fixed_id


def test_chat_empty_message_rejected(client_no_key):
    r = client_no_key.post("/api/v1/chat", json={"message": ""})
    assert r.status_code == 422


def test_chat_response_shape(client_no_key):
    r = client_no_key.post("/api/v1/chat", json={"message": "some opportunity"})
    body = r.json()
    required_keys = {"conversation_id", "answer", "matched_units", "suggestions", "analysis_card", "suggested_actions"}
    assert required_keys.issubset(body.keys())


# ── intent routing tests ───────────────────────────────────────────────────────


def test_chat_intent_find_units_calls_matching(client_with_context):
    """intent=find_units → run_matching called, response has matched_units."""
    extract = OpportunityExtract(title="D365 Japan", market="Japan", tech_stack=["D365"])
    ctx = _make_context(ChatIntent.find_units, DetectedLanguage.vi)

    with (
        patch("app.api.routes.chat.analyze_context", return_value=ctx),
        patch("app.api.routes.chat.run_matching",
              return_value=(extract, _FAKE_MATCHED, _FAKE_SUGGESTIONS, "Tôi tìm thấy 1 đơn vị.")),
        patch("app.api.routes.chat.settings") as ms,
    ):
        ms.llm_api_key = "fake-key"
        r = client_with_context.post("/api/v1/chat", json={"message": "D365 Japan retail"})

    assert r.status_code == 200
    body = r.json()
    assert len(body["matched_units"]) == 1
    assert body["matched_units"][0]["unit_name"] == "D365 Division"
    assert body["matched_units"][0]["fit_level"] == "high"
    assert len(body["suggestions"]) == 1
    assert body["suggestions"][0]["match_level"] == "High"
    assert body["analysis_card"]["footer_hint"] is not None
    # suggested_actions for find_units with results
    assert "save_opportunity_draft" in body["suggested_actions"]
    assert "request_deal_form" in body["suggested_actions"]
    # context echoed back
    assert body["context"]["intent"] == "find_units"
    assert body["context"]["language"] == "vi"


def test_chat_intent_find_units_language_passed_to_matching(client_with_context):
    """run_matching should receive the language from ConversationContext."""
    extract = OpportunityExtract(title="Azure", tech_stack=["Azure"])
    ctx = _make_context(ChatIntent.find_units, DetectedLanguage.en)

    mock_run = MagicMock(return_value=(extract, [], [], "No units found."))

    with (
        patch("app.api.routes.chat.analyze_context", return_value=ctx),
        patch("app.api.routes.chat.run_matching", mock_run),
        patch("app.api.routes.chat.settings") as ms,
    ):
        ms.llm_api_key = "fake-key"
        client_with_context.post("/api/v1/chat", json={"message": "Azure project"})

    mock_run.assert_called_once()
    call_kwargs = mock_run.call_args.kwargs
    assert call_kwargs.get("language") == DetectedLanguage.en


def test_chat_intent_chitchat_no_matching(client_with_context):
    """intent=chitchat → run_matching NOT called, suggested_actions empty."""
    ctx = _make_context(ChatIntent.chitchat, DetectedLanguage.vi)

    with (
        patch("app.api.routes.chat.analyze_context", return_value=ctx),
        patch("app.api.routes.chat.run_matching") as mock_run,
        patch("app.api.routes.chat.settings") as ms,
    ):
        ms.llm_api_key = "fake-key"
        r = client_with_context.post("/api/v1/chat", json={"message": "Xin chào!"})

    mock_run.assert_not_called()
    body = r.json()
    assert r.status_code == 200
    assert body["suggested_actions"] == []
    assert body["context"]["intent"] == "chitchat"


def test_chat_intent_clarify_returns_question(client_with_context):
    """intent=clarify → answer = clarification_needed question."""
    ctx = _make_context(ChatIntent.clarify, DetectedLanguage.vi)

    with (
        patch("app.api.routes.chat.analyze_context", return_value=ctx),
        patch("app.api.routes.chat.run_matching") as mock_run,
        patch("app.api.routes.chat.settings") as ms,
    ):
        ms.llm_api_key = "fake-key"
        r = client_with_context.post("/api/v1/chat", json={"message": "help"})

    mock_run.assert_not_called()
    body = r.json()
    assert r.status_code == 200
    assert "Bạn muốn tìm gì?" in body["answer"]


def test_chat_intent_request_deal_form(client_with_context):
    """intent=request_deal_form → suggested_actions contains submit_deal_form."""
    ctx = _make_context(ChatIntent.request_deal_form, DetectedLanguage.vi)

    with (
        patch("app.api.routes.chat.analyze_context", return_value=ctx),
        patch("app.api.routes.chat.run_matching") as mock_run,
        patch("app.api.routes.chat.settings") as ms,
    ):
        ms.llm_api_key = "fake-key"
        r = client_with_context.post("/api/v1/chat", json={"message": "tạo deal HubSpot"})

    mock_run.assert_not_called()
    body = r.json()
    assert r.status_code == 200
    assert "submit_deal_form" in body["suggested_actions"]


def test_chat_intent_unknown_returns_rephrase_message(client_with_context):
    """intent=unknown → answer asks user to rephrase."""
    ctx = _make_context(ChatIntent.unknown, DetectedLanguage.en)

    with (
        patch("app.api.routes.chat.analyze_context", return_value=ctx),
        patch("app.api.routes.chat.settings") as ms,
    ):
        ms.llm_api_key = "fake-key"
        r = client_with_context.post("/api/v1/chat", json={"message": "???"})

    assert r.status_code == 200
    body = r.json()
    assert body["suggested_actions"] == []


def test_chat_context_analysis_failure_falls_back_to_stub(client_with_context):
    """analyze_context exception → stub response, not 500."""
    with (
        patch("app.api.routes.chat.analyze_context", side_effect=RuntimeError("LLM down")),
        patch("app.api.routes.chat.settings") as ms,
    ):
        ms.llm_api_key = "fake-key"
        r = client_with_context.post("/api/v1/chat", json={"message": "anything"})

    assert r.status_code == 200
    body = r.json()
    assert "conversation_id" in body


def test_chat_matching_exception_falls_back_to_stub(client_with_context):
    """run_matching exception → stub response, not 500."""
    ctx = _make_context(ChatIntent.find_units)

    with (
        patch("app.api.routes.chat.analyze_context", return_value=ctx),
        patch("app.api.routes.chat.run_matching", side_effect=RuntimeError("agent crashed")),
        patch("app.api.routes.chat.settings") as ms,
    ):
        ms.llm_api_key = "fake-key"
        r = client_with_context.post("/api/v1/chat", json={"message": "anything"})

    assert r.status_code == 200
    body = r.json()
    assert "conversation_id" in body


# ── conversation CRUD tests ────────────────────────────────────────────────────


def test_create_conversation():
    from app.api.deps import get_session, require_active_user

    app.dependency_overrides[require_active_user] = _auth_override
    app.dependency_overrides[get_session] = _session_override()
    try:
        c = TestClient(app)
        r = c.post(
            "/api/v1/chat/conversations",
            json={"first_message": "We have a D365 project for Japan retail."},
        )
        assert r.status_code == 201
        body = r.json()
        assert "id" in body
        assert "created_at" in body
        assert body["title"]  # title should be generated (or fallback)
    finally:
        app.dependency_overrides.clear()


def test_list_conversations():
    from app.api.deps import get_session, require_active_user

    app.dependency_overrides[require_active_user] = _auth_override
    app.dependency_overrides[get_session] = _session_override()
    try:
        c = TestClient(app)
        r = c.get("/api/v1/chat/conversations")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
    finally:
        app.dependency_overrides.clear()


def test_get_conversation_history():
    from app.api.deps import get_session, require_active_user

    app.dependency_overrides[require_active_user] = _auth_override
    app.dependency_overrides[get_session] = _session_override(_FAKE_CONV_ID)
    try:
        c = TestClient(app)
        r = c.get(f"/api/v1/chat/conversations/{_FAKE_CONV_ID}")
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == str(_FAKE_CONV_ID)
        assert "messages" in body
    finally:
        app.dependency_overrides.clear()

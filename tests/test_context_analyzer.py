"""Unit tests for the context analyzer (LLM call 0).

All tests mock the LLM — no external services required.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from app.ai.agents.context_analyzer import (
    _build_history_summary,
    _fallback_context,
    analyze_context,
)
from app.schemas.chat import ChatMessage
from app.schemas.context import (
    ChatIntent,
    ConversationContext,
    DetectedLanguage,
    SessionMeta,
)

# ── helpers ────────────────────────────────────────────────────────────────────


def _make_llm_response(payload: dict) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = json.dumps(payload)
    return mock_resp


def _make_client(payload: dict) -> MagicMock:
    client = MagicMock()
    client.chat.completions.create.return_value = _make_llm_response(payload)
    return client


# ── _build_history_summary ────────────────────────────────────────────────────


def test_build_history_summary_empty():
    assert _build_history_summary([]) == "(no prior turns)"


def test_build_history_summary_formats_turns():
    history = [
        ChatMessage(role="user", content="Hello"),
        ChatMessage(role="assistant", content="Hi there"),
    ]
    result = _build_history_summary(history)
    assert "[user] Hello" in result
    assert "[assistant] Hi there" in result


def test_build_history_summary_limits_to_last_4():
    history = [
        ChatMessage(role="user", content=f"msg {i}")
        for i in range(10)
    ]
    result = _build_history_summary(history)
    # Only the last 4 turns
    assert "msg 9" in result
    assert "msg 0" not in result


def test_build_history_summary_truncates_long_content():
    long_msg = "x" * 400
    history = [ChatMessage(role="user", content=long_msg)]
    result = _build_history_summary(history)
    assert len(result) < 400  # truncated at 300 chars per message


# ── _fallback_context ─────────────────────────────────────────────────────────


def test_fallback_context_defaults():
    ctx = _fallback_context("test message")
    assert ctx.intent == ChatIntent.unknown
    assert ctx.language == DetectedLanguage.vi
    assert ctx.confidence == 0.0
    assert ctx.raw_message == "test message"
    assert ctx.opportunity_hint is None
    assert ctx.clarification_needed is None


# ── analyze_context ───────────────────────────────────────────────────────────


def test_analyze_context_find_units():
    llm_payload = {
        "intent": "find_units",
        "language": "vi",
        "confidence": 0.95,
        "opportunity_hint": "D365 project for Japan retail",
        "clarification_needed": None,
    }
    with patch("app.ai.agents.context_analyzer._llm_client", return_value=_make_client(llm_payload)):
        ctx = analyze_context("Tìm đơn vị D365 cho dự án Nhật", [])

    assert ctx.intent == ChatIntent.find_units
    assert ctx.language == DetectedLanguage.vi
    assert ctx.confidence == 0.95
    assert ctx.opportunity_hint == "D365 project for Japan retail"
    assert ctx.clarification_needed is None
    assert ctx.raw_message == "Tìm đơn vị D365 cho dự án Nhật"


def test_analyze_context_english_message():
    llm_payload = {
        "intent": "find_units",
        "language": "en",
        "confidence": 0.9,
        "opportunity_hint": "Azure migration for fintech",
        "clarification_needed": None,
    }
    with patch("app.ai.agents.context_analyzer._llm_client", return_value=_make_client(llm_payload)):
        ctx = analyze_context("We need Azure migration for fintech client", [])

    assert ctx.language == DetectedLanguage.en
    assert ctx.intent == ChatIntent.find_units


def test_analyze_context_chitchat():
    llm_payload = {
        "intent": "chitchat",
        "language": "vi",
        "confidence": 0.98,
        "opportunity_hint": None,
        "clarification_needed": None,
    }
    with patch("app.ai.agents.context_analyzer._llm_client", return_value=_make_client(llm_payload)):
        ctx = analyze_context("Xin chào!", [])

    assert ctx.intent == ChatIntent.chitchat
    assert ctx.opportunity_hint is None  # cleared for non-find_units


def test_analyze_context_clarify_populates_question():
    llm_payload = {
        "intent": "clarify",
        "language": "vi",
        "confidence": 0.7,
        "opportunity_hint": None,
        "clarification_needed": "Bạn muốn tìm đơn vị nào?",
    }
    with patch("app.ai.agents.context_analyzer._llm_client", return_value=_make_client(llm_payload)):
        ctx = analyze_context("help", [])

    assert ctx.intent == ChatIntent.clarify
    assert ctx.clarification_needed == "Bạn muốn tìm đơn vị nào?"


def test_analyze_context_unknown_intent_clamped():
    """LLM returns an intent value not in the enum — should clamp to unknown."""
    llm_payload = {
        "intent": "fly_to_moon",
        "language": "en",
        "confidence": 0.5,
        "opportunity_hint": None,
        "clarification_needed": None,
    }
    with patch("app.ai.agents.context_analyzer._llm_client", return_value=_make_client(llm_payload)):
        ctx = analyze_context("Do something weird", [])

    assert ctx.intent == ChatIntent.unknown


def test_analyze_context_unknown_language_clamped():
    """LLM returns an unrecognised language code — should clamp to vi."""
    llm_payload = {
        "intent": "chitchat",
        "language": "klingon",
        "confidence": 0.5,
        "opportunity_hint": None,
        "clarification_needed": None,
    }
    with patch("app.ai.agents.context_analyzer._llm_client", return_value=_make_client(llm_payload)):
        ctx = analyze_context("Hello", [])

    assert ctx.language == DetectedLanguage.vi


def test_analyze_context_confidence_clamped():
    """Confidence outside [0, 1] should be clamped."""
    llm_payload = {
        "intent": "find_units",
        "language": "en",
        "confidence": 99.0,
        "opportunity_hint": "big project",
        "clarification_needed": None,
    }
    with patch("app.ai.agents.context_analyzer._llm_client", return_value=_make_client(llm_payload)):
        ctx = analyze_context("Big project for us", [])

    assert ctx.confidence == 1.0


def test_analyze_context_llm_exception_returns_fallback():
    client = MagicMock()
    client.chat.completions.create.side_effect = RuntimeError("LLM down")

    with patch("app.ai.agents.context_analyzer._llm_client", return_value=client):
        ctx = analyze_context("Any message", [])

    assert ctx.intent == ChatIntent.unknown
    assert ctx.confidence == 0.0


def test_analyze_context_uses_session_meta_language_hint():
    """session_meta language hint should be included in the prompt (verify via call args)."""
    llm_payload = {
        "intent": "find_units",
        "language": "ja",
        "confidence": 0.88,
        "opportunity_hint": "D365 project",
        "clarification_needed": None,
    }
    client = _make_client(llm_payload)
    meta = SessionMeta(language=DetectedLanguage.ja)

    with patch("app.ai.agents.context_analyzer._llm_client", return_value=client):
        ctx = analyze_context("D365プロジェクト", [], session_meta=meta)

    # Check the prompt contained the session language hint
    call_args = client.chat.completions.create.call_args
    system_content = call_args.kwargs["messages"][0]["content"]
    assert "ja" in system_content

    assert ctx.language == DetectedLanguage.ja
    assert ctx.intent == ChatIntent.find_units


def test_analyze_context_clarification_cleared_for_non_clarify():
    """clarification_needed should be None unless intent == clarify."""
    llm_payload = {
        "intent": "find_units",
        "language": "en",
        "confidence": 0.9,
        "opportunity_hint": "some project",
        "clarification_needed": "This should be cleared",  # LLM set this erroneously
    }
    with patch("app.ai.agents.context_analyzer._llm_client", return_value=_make_client(llm_payload)):
        ctx = analyze_context("Find units for my project", [])

    assert ctx.clarification_needed is None  # cleared because intent != clarify


def test_analyze_context_returns_conversation_context_type():
    llm_payload = {
        "intent": "chitchat",
        "language": "en",
        "confidence": 0.99,
        "opportunity_hint": None,
        "clarification_needed": None,
    }
    with patch("app.ai.agents.context_analyzer._llm_client", return_value=_make_client(llm_payload)):
        ctx = analyze_context("Hi!", [])

    assert isinstance(ctx, ConversationContext)

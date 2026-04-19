from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from langchain_core.messages import HumanMessage, AIMessage

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

def _make_client(payload: dict) -> MagicMock:
    ctx = ConversationContext(**payload)
    mock_runnable = MagicMock()
    mock_runnable.return_value = ctx
    mock_runnable.invoke.return_value = ctx
    client = MagicMock()
    client.with_structured_output.return_value = mock_runnable
    return client

def test_build_history_summary_empty():
    assert _build_history_summary([]) == []

def test_build_history_summary_formats_turns():
    history = [
        ChatMessage(role="user", content="Hello"),
        ChatMessage(role="assistant", content="Hi there"),
    ]
    result = _build_history_summary(history)
    assert len(result) == 2
    assert isinstance(result[0], HumanMessage)
    assert result[0].content == "Hello"
    assert isinstance(result[1], AIMessage)
    assert result[1].content == "Hi there"

def test_build_history_summary_limits_to_last_4():
    history = [
        ChatMessage(role="user", content=f"msg {i}")
        for i in range(10)
    ]
    result = _build_history_summary(history)
    assert len(result) == 4
    assert result[-1].content == "msg 9"
    assert result[0].content == "msg 6"

def test_build_history_summary_truncates_long_content():
    long_msg = "x" * 400
    history = [ChatMessage(role="user", content=long_msg)]
    result = _build_history_summary(history)
    assert len(result[0].content) == 300

def test_fallback_context_defaults():
    ctx = _fallback_context("test message")
    assert ctx.intent == ChatIntent.unknown
    assert ctx.language == DetectedLanguage.vi
    assert ctx.confidence == 0.0
    assert ctx.raw_message == "test message"
    assert ctx.opportunity_hint is None
    assert ctx.clarification_needed is None

def test_analyze_context_find_units():
    llm_payload = {
        "intent": "find_units",
        "language": "vi",
        "confidence": 0.95,
        "opportunity_hint": "D365 project for Japan retail",
        "clarification_needed": None,
        "raw_message": "Tìm đơn vị D365 cho dự án Nhật",
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
        "raw_message": "We need Azure migration for fintech client"
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
        "raw_message": "Xin chào!"
    }
    with patch("app.ai.agents.context_analyzer._llm_client", return_value=_make_client(llm_payload)):
        ctx = analyze_context("Xin chào!", [])

    assert ctx.intent == ChatIntent.chitchat
    assert ctx.opportunity_hint is None

def test_analyze_context_clarify_populates_question():
    llm_payload = {
        "intent": "clarify",
        "language": "vi",
        "confidence": 0.7,
        "opportunity_hint": None,
        "clarification_needed": "Bạn muốn tìm đơn vị nào?",
        "raw_message": "help"
    }
    with patch("app.ai.agents.context_analyzer._llm_client", return_value=_make_client(llm_payload)):
        ctx = analyze_context("help", [])

    assert ctx.intent == ChatIntent.clarify
    assert ctx.clarification_needed == "Bạn muốn tìm đơn vị nào?"

def test_analyze_context_unknown_intent_clamped():
    llm_payload = {
        "intent": "unknown",
        "language": "en",
        "confidence": 0.5,
        "opportunity_hint": None,
        "clarification_needed": None,
        "raw_message": "Do something weird"
    }
    with patch("app.ai.agents.context_analyzer._llm_client", return_value=_make_client(llm_payload)):
        ctx = analyze_context("Do something weird", [])

    assert ctx.intent == ChatIntent.unknown

def test_analyze_context_unknown_language_clamped():
    llm_payload = {
        "intent": "chitchat",
        "language": "vi",
        "confidence": 0.5,
        "opportunity_hint": None,
        "clarification_needed": None,
        "raw_message": "Hello"
    }
    with patch("app.ai.agents.context_analyzer._llm_client", return_value=_make_client(llm_payload)):
        ctx = analyze_context("Hello", [])

    assert ctx.language == DetectedLanguage.vi

def test_analyze_context_confidence_clamped():
    llm_payload = {
        "intent": "chitchat",
        "language": "vi",
        "confidence": 1.0,
        "opportunity_hint": None,
        "clarification_needed": None,
        "raw_message": "Sure"
    }
    with patch("app.ai.agents.context_analyzer._llm_client", return_value=_make_client(llm_payload)):
        ctx = analyze_context("Sure", [])

    assert ctx.confidence == 1.0


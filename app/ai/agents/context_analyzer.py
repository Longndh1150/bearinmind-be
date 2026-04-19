"""Context Analyzer — LLM call 0 in every chat turn.

Classifies the user's intent and detects the language before any tool is called.
The result (ConversationContext) drives routing in app/api/routes/chat.py.
"""

from __future__ import annotations

import logging
from typing import Literal

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage

from app.ai.prompts.context import classify_intent_prompt
from app.core.config import settings
from app.schemas.chat import ChatMessage
from app.schemas.context import (
    ChatIntent,
    ConversationContext,
    DetectedLanguage,
    SessionMeta,
)

logger = logging.getLogger(__name__)

# Maximum number of recent turns to include in history_summary
_HISTORY_TURNS = 4


def _llm_client() -> ChatOpenAI:
    kwargs: dict = {"api_key": settings.llm_api_key or "no-key"}
    if settings.llm_base_url:
        kwargs["base_url"] = settings.llm_base_url
    return ChatOpenAI(**kwargs, model=settings.llm_model_secondary)


def _build_history_summary(history: list[ChatMessage]) -> list:
    """Convert last N turns to a list of LangChain messages."""
    if not history:
        return []
    recent = history[-_HISTORY_TURNS:]
    out = []
    for m in recent:
        if m.role == "user":
            out.append(HumanMessage(content=m.content[:300]))
        elif m.role == "assistant":
            out.append(AIMessage(content=m.content[:300]))
    return out


def _fallback_context(message: str) -> ConversationContext:
    """Return a safe fallback when the LLM call fails."""
    return ConversationContext(
        intent=ChatIntent.unknown,
        language=DetectedLanguage.vi,
        confidence=0.0,
        opportunity_hint=None,
        clarification_needed=None,
        raw_message=message,
    )


def analyze_context(
    message: str,
    history: list[ChatMessage],
    session_meta: SessionMeta | None = None,
) -> ConversationContext:
    """LLM call 0: classify intent + detect language.

    Args:
        message: The current user message.
        history: Recent chat history (stateless clients may pass []).
        session_meta: Persisted session metadata from prior turns. Used to hint
                      at the prior language so the LLM stays consistent.

    Returns:
        ConversationContext with intent, language, confidence, and optional
        opportunity_hint / clarification_needed fields.
    """
    session_language = session_meta.language.value if session_meta else "unknown"
    history_msgs = _build_history_summary(history)

    client = _llm_client()
    chain = classify_intent_prompt | client.with_structured_output(ConversationContext)

    try:
        ctx: ConversationContext = chain.invoke({
            "message": message,
            "history": history_msgs,
            "session_language": session_language,
        })
        
        # Enforce field semantics
        if ctx.intent != ChatIntent.clarify:
            ctx.clarification_needed = None
        if ctx.intent not in (ChatIntent.find_units, ChatIntent.save_draft):
            ctx.opportunity_hint = None
            
        ctx.raw_message = message
        return ctx
    except Exception:
        logger.exception("Context analysis LLM call failed; using fallback")
        return _fallback_context(message)


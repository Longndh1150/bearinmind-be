"""Context Analyzer — LLM call 0 in every chat turn.

Classifies the user's intent and detects the language before any tool is called.
The result (ConversationContext) drives routing in app/api/routes/chat.py.
"""

from __future__ import annotations

import json
import logging

from openai import OpenAI

from app.ai.prompts.context import CLASSIFY_INTENT_SYSTEM
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


def _llm_client() -> OpenAI:
    kwargs: dict = {"api_key": settings.llm_api_key or "no-key"}
    if settings.llm_base_url:
        kwargs["base_url"] = settings.llm_base_url
    return OpenAI(**kwargs)


def _build_history_summary(history: list[ChatMessage]) -> str:
    """Convert last N turns to a compact string for the prompt."""
    if not history:
        return "(no prior turns)"
    recent = history[-_HISTORY_TURNS:]
    lines = [f"[{m.role}] {m.content[:300]}" for m in recent]
    return "\n".join(lines)


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
    history_summary = _build_history_summary(history)

    system_prompt = CLASSIFY_INTENT_SYSTEM.format(
        message=message,
        history_summary=history_summary,
        session_language=session_language,
    )

    client = _llm_client()
    try:
        resp = client.chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "system", "content": system_prompt}],
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or "{}"
        data = json.loads(raw)
    except Exception:
        logger.exception("Context analysis LLM call failed; using fallback")
        return _fallback_context(message)

    # Validate / coerce LLM output into the schema.
    # Unknown enum values are clamped to the fallback rather than raising.
    try:
        intent_raw = data.get("intent", "unknown")
        intent = ChatIntent(intent_raw) if intent_raw in ChatIntent._value2member_map_ else ChatIntent.unknown

        lang_raw = data.get("language", "vi")
        language = DetectedLanguage(lang_raw) if lang_raw in DetectedLanguage._value2member_map_ else DetectedLanguage.vi

        confidence = float(data.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))

        opportunity_hint: str | None = data.get("opportunity_hint") or None
        clarification_needed: str | None = data.get("clarification_needed") or None

        # Enforce field semantics: only populate the relevant optional field
        if intent != ChatIntent.clarify:
            clarification_needed = None
        if intent not in (ChatIntent.find_units, ChatIntent.save_draft):
            opportunity_hint = None

        return ConversationContext(
            intent=intent,
            language=language,
            confidence=confidence,
            opportunity_hint=opportunity_hint,
            clarification_needed=clarification_needed,
            raw_message=message,
        )
    except Exception:
        logger.exception("Context schema validation failed; using fallback")
        return _fallback_context(message)

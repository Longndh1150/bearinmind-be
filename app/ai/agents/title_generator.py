"""Conversation title generator — uses the secondary (lightweight) LLM model.

Generates a short, descriptive title for a new conversation based on the
user's first message. Called after the first chat turn to name the session.
"""

from __future__ import annotations

import logging

from openrouter import OpenRouter

from app.core.config import settings

logger = logging.getLogger(__name__)

_MAX_TITLE_LEN = 60


from app.core.llm_tracking import instrument_openrouter_client


def _llm_client() -> OpenRouter:
    return instrument_openrouter_client(OpenRouter(api_key=settings.llm_api_key or "no-key"))


def generate_title(first_message: str) -> str:
    """Generate a short conversation title from the user's first message.

    Uses `llm_model_secondary` to keep cost/latency low.
    Falls back to a truncated version of the message if the LLM call fails.

    Args:
        first_message: The user's opening message in the conversation.

    Returns:
        A short title string (≤ 60 chars), no trailing punctuation.
    """
    if not settings.llm_api_key:
        return _fallback_title(first_message)

    system = (
        "You are a concise title generator for a sales AI assistant chat. "
        "Given the user's first message, produce a SHORT title (5–10 words max) "
        "that captures the main topic. "
        "Rules:\n"
        "- No quotes, no leading/trailing punctuation.\n"
        "- Match the language of the user's message (Vietnamese → Vietnamese title, etc.).\n"
        "- Output ONLY the title text, nothing else.\n"
        "- Maximum 60 characters."
    )

    client = _llm_client()
    try:
        resp = client.chat.send(
            model=settings.llm_model_secondary,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": first_message[:1000]},
            ],
            temperature=0.3,
        )
        raw = (resp.choices[0].message.content or "").strip().strip('"\'')
        title = raw[:_MAX_TITLE_LEN] if raw else _fallback_title(first_message)
        logger.debug("Generated title: %r", title)
        return title
    except Exception:
        logger.warning("Title generation LLM call failed; using fallback")
        return _fallback_title(first_message)


def _fallback_title(message: str) -> str:
    """Truncate the message to produce a simple fallback title."""
    clean = message.strip()
    if len(clean) <= _MAX_TITLE_LEN:
        return clean
    return clean[: _MAX_TITLE_LEN - 1] + "…"

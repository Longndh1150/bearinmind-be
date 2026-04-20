"""Schemas for conversation context analysis (intent classification, language detection)."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChatIntent(StrEnum):
    """All recognized user intents, mapped to downstream flows."""

    # US1: user describes an opportunity and wants to find matching divisions
    find_units = "find_units"
    # US1: user wants to send notify/connect to a unit
    send_notification = "send_notification"
    # US5: user explicitly asks to save/persist the discussed opportunity as a draft
    save_draft = "save_draft"
    # US5: user wants to create a HubSpot deal — FE will show the deal form
    request_deal_form = "request_deal_form"
    # US3: user (D.Lead) wants to update their unit's capabilities
    update_capabilities = "update_capabilities"
    # greeting, thanks, off-topic — no tool needed
    chitchat = "chitchat"
    # message too vague; AI should ask a follow-up question
    clarify = "clarify"
    # none of the above; safe fallback
    unknown = "unknown"


class DetectedLanguage(StrEnum):
    vi = "vi"       # Vietnamese
    en = "en"       # English
    ja = "ja"       # Japanese
    other = "other"
    unknown = "unknown"


class ConversationContext(BaseModel):
    """Output of the context analysis step (LLM call 0 in each chat turn).

    Contains everything the router needs to decide which tool/flow to run.
    """

    model_config = ConfigDict(extra="forbid")

    intent: ChatIntent
    language: DetectedLanguage
    # 0.0–1.0 confidence in the intent classification
    confidence: float = Field(ge=0.0, le=1.0, examples=[0.92])

    # Brief summary of the opportunity if the user described one; null otherwise.
    # Used by find_units and save_draft flows as a compact query hint.
    opportunity_hint: str | None = Field(
        default=None,
        max_length=500,
        description="Short summary of the opportunity described by the user, if any.",
    )

    # When intent == clarify, the question the AI should ask back.
    clarification_needed: str | None = Field(
        default=None,
        max_length=500,
        description="Follow-up question for the user when the message is too vague.",
    )

    # Always carries the raw message so downstream tools can use it directly.
    raw_message: str = Field(min_length=1, max_length=20_000)


class SessionMeta(BaseModel):
    """Persistent metadata stored on the Conversation row (JSONB column).

    Survives across multiple turns so language and draft state are not re-detected
    every time.
    """

    model_config = ConfigDict(extra="ignore")  # forward-compatible

    language: DetectedLanguage = DetectedLanguage.vi
    last_intent: ChatIntent = ChatIntent.unknown
    # UUID of the in-progress opportunity draft, if one has been saved this session
    opportunity_draft_id: UUID | None = None
    
    # Danh sách các đơn vị đã được suggest trong session này (để lookup UUID khi user yêu cầu notification)
    # Lưu dạng list dict, ví dụ: [{"id": "...", "name": "DN1", "user_id": "head_user_id"}]
    suggested_units: list[dict] = Field(default_factory=list)


__all__ = [
    "ChatIntent",
    "ConversationContext",
    "DetectedLanguage",
    "SessionMeta",
]

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.llm import OpportunityExtract

ChatRole = Literal["user", "assistant", "tool"]
AnalysisTagTone = Literal["purple", "teal", "amber"]
CapabilityTagTone = Literal["teal", "gray", "success", "warning"]
MatchLevel = Literal["High", "Medium"]


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: ChatRole
    content: str = Field(min_length=1, max_length=20_000)
    created_at: datetime | None = None


class OpportunityAnalysisCard(BaseModel):
    """Optional summary block above team cards (mirrors FE design)."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200, examples=["Phân tích cơ hội mới"])
    tags: list[dict[str, str]] = Field(
        default_factory=list,
        description="List of tags for quick scanning. Each tag has {label, tone}.",
        examples=[
            [
                {"label": "Microsoft Dynamics 365", "tone": "purple"},
                {"label": "Nhật Bản", "tone": "teal"},
                {"label": "Cần Senior + Proposal", "tone": "amber"},
            ]
        ],
    )
    footer_hint: str | None = Field(
        default=None,
        max_length=300,
        description="Small hint text at the bottom of analysis card.",
    )


class TeamSuggestion(BaseModel):
    """Rich suggestion card payload to render interactive UI on FE."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    match_level: MatchLevel
    tech_stack: list[str] = Field(default_factory=list)
    case_studies: list[str] = Field(default_factory=list)
    contact: str = Field(min_length=1, max_length=200)

    suggestion_rank: str | None = Field(default=None, max_length=50, examples=["Đề xuất 1"])
    summary: str | None = Field(default=None, max_length=1000)

    contact_role: str | None = Field(default=None, max_length=50, examples=["SL", "DL"])
    contact_short_name: str | None = Field(default=None, max_length=100, examples=["ThangLB"])

    capability_tags: list[dict[str, str]] | None = Field(
        default=None,
        description="Styled capability/resource tags: each tag has {label, tone}.",
        examples=[[{"label": "3 Senior", "tone": "teal"}, {"label": "Có Senior chuyên sâu", "tone": "success"}]],
    )
    variant: Literal["primary", "secondary"] | None = Field(
        default=None,
        description="FE styling hint.",
        examples=["primary"],
    )


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: UUID | None = Field(
        default=None,
        description="If provided, continues an existing conversation; otherwise server creates one.",
    )
    message: str = Field(min_length=1, max_length=20_000, examples=["We have a D365 project for Japan retail."])
    history: list[ChatMessage] = Field(
        default_factory=list,
        description="Optional recent chat history for stateless clients; server may ignore if it stores history.",
    )

    # Controls
    allow_crm_write: bool = Field(
        default=False,
        description="If true, server may propose CRM sync actions, but must still require explicit confirmation.",
    )


class MatchRationale(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=1000)
    evidence: list[str] = Field(default_factory=list, description="Bullet reasons supporting the match.")
    confidence: float = Field(ge=0, le=1, examples=[0.82])


class MatchedUnit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit_id: UUID
    unit_name: str = Field(min_length=1, max_length=200)
    contact_name: str = Field(min_length=1, max_length=200)
    contact_email: str | None = Field(default=None, max_length=320)
    fit_level: Literal["high", "medium", "low"] = Field(examples=["high"])
    rationale: MatchRationale


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: UUID
    answer: str = Field(min_length=1, max_length=20_000)

    extracted_opportunity: OpportunityExtract | None = Field(
        default=None,
        description="Best-effort structured extraction from user message.",
    )
    matched_units: list[MatchedUnit] = Field(default_factory=list)
    analysis_card: OpportunityAnalysisCard | None = Field(
        default=None,
        description="Optional analysis summary card for FE to render above suggestions.",
    )
    suggestions: list[TeamSuggestion] = Field(
        default_factory=list,
        description="Optional rich suggestion cards for FE (interactive UI).",
    )

    suggested_actions: list[str] = Field(
        default_factory=list,
        description="Client-facing next actions like 'save opportunity draft', 'push to CRM', etc.",
    )


__all__ = [
    "AnalysisTagTone",
    "CapabilityTagTone",
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "ChatRole",
    "MatchLevel",
    "MatchedUnit",
    "MatchRationale",
    "OpportunityAnalysisCard",
    "TeamSuggestion",
]


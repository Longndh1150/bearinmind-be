from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.schemas.common import AuditFields, SourceRef

OpportunityStatus = Literal["draft", "open", "won", "lost", "archived"]
OpportunitySource = Literal["chat", "hubspot", "manual"]


class OpportunityParty(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    website: HttpUrl | None = None
    country: str | None = Field(default=None, max_length=100)


class OpportunityExtracted(BaseModel):
    """Structured attributes extracted from free text (LLM/tool assisted)."""

    model_config = ConfigDict(extra="forbid")

    industry: str | None = Field(default=None, max_length=200)
    market: str | None = Field(default=None, max_length=100, examples=["Japan"])
    tech_stack: list[str] = Field(default_factory=list, examples=[["D365", "Power Platform"]])
    budget: str | None = Field(default=None, max_length=100, examples=["$100k - $200k"])
    scale: str | None = Field(default=None, max_length=100, examples=["10-15 engineers"])


class OpportunityCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: OpportunitySource = Field(default="chat")
    title: str = Field(min_length=1, max_length=200, examples=["D365 implementation for retail client"])
    description: str = Field(min_length=1, max_length=10_000)
    client: OpportunityParty | None = None

    extracted: OpportunityExtracted | None = Field(
        default=None,
        description="Optional structured fields if already extracted client-side; server may re-evaluate.",
    )


class OpportunityUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=10_000)
    client: OpportunityParty | None = None
    extracted: OpportunityExtracted | None = None
    status: OpportunityStatus | None = None


class OpportunityPublic(AuditFields):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    title: str
    description: str
    status: OpportunityStatus = "draft"

    source_ref: SourceRef
    is_official: bool = False
    pushed_at: datetime | None = None

    client: OpportunityParty | None = None
    extracted: OpportunityExtracted | None = None


class OpportunityListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)

    status: OpportunityStatus | None = None
    source: OpportunitySource | None = None
    unit_id: UUID | None = None
    q: str | None = Field(default=None, max_length=200, description="Free text search query.")


class OpportunityPushCrmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: bool = Field(
        default=False,
        description="Must be true to execute CRM write.",
        examples=[True],
    )


class OpportunityPushCrmResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool
    source: OpportunitySource = Field(default="hubspot")
    external_id: str | None = Field(default=None, description="HubSpot deal id when success.")
    message: str = Field(examples=["Pushed to HubSpot"])


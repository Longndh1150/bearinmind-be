from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class APIError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(
        description="Machine-readable error code.",
        examples=["auth.invalid_credentials", "validation.failed", "resource.not_found"],
    )
    message: str = Field(description="Human-readable message.", examples=["Invalid credentials"])
    request_id: str | None = Field(default=None, description="Optional trace/request id for debugging.")
    details: dict[str, Any] | None = Field(
        default=None,
        description="Optional structured details to help clients handle the error.",
    )


class Paginated[T](BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[T]
    total: int = Field(ge=0, description="Total number of matching items.")
    limit: int = Field(ge=1, le=200)
    offset: int = Field(ge=0)


class AuditFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    created_at: datetime
    updated_at: datetime | None = None


class ActorRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID | None = None
    email: str | None = None


class SourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["chat", "hubspot", "manual"] = Field(
        description="Where this record came from.",
        examples=["chat"],
    )
    external_id: str | None = Field(
        default=None,
        description="External id if sourced from an integration (e.g. HubSpot deal id).",
    )


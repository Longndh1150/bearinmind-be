from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import AuditFields


class NotificationPublic(AuditFields):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    type: Literal["opportunity_match"] = Field(default="opportunity_match")
    fit_level: Literal["high", "medium"] = Field(examples=["high"])
    is_read: bool = Field(default=False)
    read_at: datetime | None = None

    opportunity_id: UUID
    unit_id: UUID | None = None

    title: str = Field(min_length=1, max_length=200, examples=["Opportunity matches your unit"])
    message: str = Field(min_length=1, max_length=2000)


class NotificationListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    unread_only: bool = Field(default=False)


class NotificationMarkReadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_read: bool = Field(default=True)


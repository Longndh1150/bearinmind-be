from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import AuditFields


class NotificationPublic(AuditFields):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    type: str = Field(default="opportunity_match", examples=["opportunity_match_unit"])
    fit_level: str = Field(default="medium", examples=["high"])
    is_read: bool = Field(default=False)
    read_at: datetime | None = None

    opportunity_id: UUID | None = None
    unit_id: UUID | None = None

    title: str = Field(min_length=1, max_length=200, examples=["Opportunity matches your unit"])
    message: str = Field(min_length=1, max_length=2000)
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Type-specific notification data for FE rendering.",
    )


class NotificationListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    unread_only: bool = Field(default=False)


class NotificationMarkReadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_read: bool = Field(default=True)


class OpportunityMatchUnitNotificationDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opportunity_name: str = Field(min_length=1, max_length=200, examples=["ABC"])
    customer_group: str | None = Field(default=None, examples=["JP"])
    deadline: datetime | None = None
    required_tech: list[str] = Field(default_factory=list, examples=[["Java"]])
    next_steps: str | None = None
    special_requirements: str | None = None
    bear_message: str | None = Field(
        default=None,
        description="Short guidance text for the bear icon in FE.",
        examples=["Deadline này khá gấp, ưu tiên confirm resource trong hôm nay."],
    )
    sales_contact_name: str | None = Field(default=None, examples=["Nguyen Van A"])
    sales_contact_email: str | None = Field(default=None, examples=["a.nguyen@rikkei.com"])
    sales_contact_phone: str | None = Field(default=None, examples=["+84 901 234 567"])


class NotificationCreateOpportunityMatchUnitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipient_user_id: UUID
    opportunity_id: UUID | None = None
    unit_id: UUID | None = None
    fit_level: Literal["high", "medium", "low"] = Field(default="medium")
    title: str = Field(
        default="Opportunity match for your unit",
        min_length=1,
        max_length=200,
    )
    message: str = Field(
        min_length=1,
        max_length=2000,
        examples=["Có cơ hội mới phù hợp với đơn vị, vui lòng review và liên hệ sales."],
    )
    details: OpportunityMatchUnitNotificationDetails


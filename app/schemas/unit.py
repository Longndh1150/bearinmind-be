from __future__ import annotations

from datetime import date
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.schemas.common import AuditFields


class UnitContact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200, examples=["Nguyen Van A"])
    email: str | None = Field(default=None, max_length=320, examples=["leader@rikkeisoft.com"])
    title: str | None = Field(default=None, max_length=200, examples=["Delivery Leader"])
    phone: str | None = Field(default=None, max_length=50, examples=["+84 9xx xxx xxx"])


class UnitExpert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200, examples=["Sin"])
    focus_areas: list[str] = Field(default_factory=list, examples=[["Azure", "DevOps"]])
    profile_url: HttpUrl | None = Field(default=None)


class UnitCaseStudy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    domain: str | None = Field(default=None, max_length=200)
    tech_stack: list[str] = Field(default_factory=list)
    url: HttpUrl | None = Field(default=None)


class UnitCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tech_stack: list[str] = Field(default_factory=list, examples=[["Java", "Spring", "AWS"]])
    experts: list[UnitExpert] = Field(default_factory=list)
    case_studies: list[UnitCaseStudy] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=2000)

    # Future integration hooks (HRM / Salekit)
    hrm_synced_at: date | None = Field(default=None)
    salekit_synced_at: date | None = Field(default=None)


class UnitPublic(AuditFields):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    code: str = Field(min_length=1, max_length=50, examples=["D365", "AI", "JAPAN"])
    name: str = Field(min_length=1, max_length=200, examples=["Rikkei D365 Division"])
    status: Literal["active", "inactive"] = Field(default="active")
    contact: UnitContact
    capabilities: UnitCapabilities


class UnitCapabilitiesUpdate(UnitCapabilities):
    model_config = ConfigDict(extra="forbid")

    # Use same fields; separated for future: partial update, versioning, confirmation, etc.
    pass


class UnitStaffAvailability(BaseModel):
    experts: list[UnitExpert]
    hrm_available_staff: list[dict[str, Any]]
    hrm_capacity: dict[str, Any]


class UnitCaseStudiesResponse(BaseModel):
    internal: list[UnitCaseStudy]
    external: list[dict[str, Any]]

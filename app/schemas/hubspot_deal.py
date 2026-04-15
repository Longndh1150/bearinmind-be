<<<<<<< HEAD
"""HubSpot deal form payload (case 2: user fills form in chat, FE POSTs JSON to BE).

Aligns with `bearinmind-fe` `DealDraft` in `src/renderer/src/types/chat.ts`.
Validation is intentionally light (length bounds, enums); no separate validate endpoint.
=======
"""HubSpot deal form payload — aligned with FE ``DealDraft`` (``bearinmind-fe/src/renderer/src/types/chat.ts``).

Validation is intentionally light (length bounds, enums); HubSpot itself
is the source of truth for property values.
>>>>>>> origin/develop
"""

from __future__ import annotations

<<<<<<< HEAD
from typing import Literal
=======
from typing import Any, Literal
>>>>>>> origin/develop

from pydantic import BaseModel, ConfigDict, Field

DealMarket = Literal["EA", "JP", "TH", "US", "KR"]

DealStatus = Literal[
    "A",
    "B",
    "C1",
    "C2",
    "D",
    "O",
    "Approaching",
    "F",
]

OnsiteOffshoreType = Literal["Onsite", "Offshore", "Onsite+Offshore"]


class HubSpotDealDraft(BaseModel):
<<<<<<< HEAD
    """User-submitted deal draft from the in-chat form (case 2)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    deal_name: str | None = Field(default=None, alias="dealName", max_length=500)
    pipeline: str | None = Field(default=None, max_length=200)
    market: DealMarket | None = None
    jp_section_lead: str | None = Field(default=None, alias="jpSectionLead", max_length=200)
    status: DealStatus | None = None
=======
    """User-submitted deal draft from the in-chat form."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    # Section 1 — Basic info
    deal_name: str | None = Field(default=None, alias="dealName", max_length=500)
    pipeline: str | None = Field(default=None, max_length=200)
    market: DealMarket | None = None
    status: DealStatus | None = None
    close_date: str | None = Field(default=None, alias="closeDate", max_length=100)
    year_of_pipeline: str | None = Field(default=None, alias="yearOfPipeline", max_length=50)

    # Section 2 — Stakeholders
    owner: str | None = Field(default=None, max_length=200)
    deal_sub_owner: str | None = Field(default=None, alias="dealSubOwner", max_length=200)
    jp_section_lead: str | None = Field(default=None, alias="jpSectionLead", max_length=200)
    ea_section_lead: str | None = Field(default=None, alias="eaSectionLead", max_length=200)
    kr_section_lead: str | None = Field(default=None, alias="krSectionLead", max_length=200)
    th_section_lead: list[str] | None = Field(default=None, alias="thSectionLead", max_length=50)
    us_section_lead: str | None = Field(default=None, alias="usSectionLead", max_length=200)
    jp_delivery_manager: str | None = Field(default=None, alias="jpDeliveryManager", max_length=200)

    # Section 3 — Deal type
    deal_type: str | None = Field(default=None, alias="dealType", max_length=100)
    contract_type: str | None = Field(default=None, alias="contractType", max_length=100)

    # Section 4 — Service details
    service_category: str | None = Field(default=None, alias="serviceCategory", max_length=100)
    service_ito_sub_category: str | None = Field(default=None, alias="serviceItoSubCategory", max_length=200)
    service_level: str | None = Field(default=None, alias="serviceLevel", max_length=200)

    # Section 5 — Delivery model
>>>>>>> origin/develop
    onsite_offshore_type: OnsiteOffshoreType | None = Field(default=None, alias="onsiteOffshoreType")
    onsite_unit_price: str | None = Field(default=None, alias="onsiteUnitPrice", max_length=200)
    offshore_unit_price: str | None = Field(default=None, alias="offshoreUnitPrice", max_length=200)
    onsite_delivery_team: list[str] | None = Field(
        default=None,
        alias="onsiteDeliveryTeam",
        max_length=50,
<<<<<<< HEAD
        description="At most 50 entries; each string trimmed by client.",
=======
>>>>>>> origin/develop
    )
    offshore_delivery_team: list[str] | None = Field(
        default=None,
        alias="offshoreDeliveryTeam",
        max_length=50,
    )
<<<<<<< HEAD
    year_of_pipeline: str | None = Field(default=None, alias="yearOfPipeline", max_length=50)
    owner: str | None = Field(default=None, max_length=200)
    deal_sub_owner: str | None = Field(default=None, alias="dealSubOwner", max_length=200)


class HubSpotDealCreateResponse(BaseModel):
    """Result after accepting draft (HubSpot create is stubbed until integration)."""
=======

    # Section 6 — Financial
    payment_period_months: str | None = Field(default=None, alias="paymentPeriodMonths", max_length=50)
    presales: str | None = Field(default=None, max_length=200)
    priority: str | None = Field(default=None, max_length=50)

    # Section 7 — Relations
    linked_company: str | None = Field(default=None, alias="linkedCompany", max_length=500)
    linked_company_label: str | None = Field(default=None, alias="linkedCompanyLabel", max_length=200)


class HubSpotDealCreateResponse(BaseModel):
    """Result after creating a deal in HubSpot."""
>>>>>>> origin/develop

    model_config = ConfigDict(extra="forbid")

    success: bool = True
    hubspot_deal_id: str | None = Field(
        default=None,
        description="HubSpot deal id when integration succeeds.",
        examples=["123456789"],
    )
<<<<<<< HEAD
    message: str = Field(default="", examples=["Deal created (stub)"])
=======
    message: str = Field(default="", examples=["Deal created successfully"])


class HubSpotDealUpdateResponse(BaseModel):
    """Result after updating a deal in HubSpot."""

    model_config = ConfigDict(extra="forbid")

    success: bool = True
    hubspot_deal_id: str
    message: str = Field(default="", examples=["Deal updated successfully"])


# ── Metadata response wrappers (pass-through from HubSpot) ───────────────────


class HubSpotPipelineStage(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str = Field(alias="stageId", default="")
    label: str = ""
    display_order: int = Field(alias="displayOrder", default=0)
    archived: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class HubSpotPipeline(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str = Field(alias="pipelineId", default="")
    label: str = ""
    display_order: int = Field(alias="displayOrder", default=0)
    archived: bool = False
    stages: list[HubSpotPipelineStage] = Field(default_factory=list)


class HubSpotPipelinesResponse(BaseModel):
    results: list[HubSpotPipeline]


class HubSpotPropertyOption(BaseModel):
    model_config = ConfigDict(extra="allow")
    label: str = ""
    value: str = ""
    display_order: int = Field(alias="displayOrder", default=0)
    hidden: bool = False


class HubSpotProperty(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str = ""
    label: str = ""
    type: str = ""
    field_type: str = Field(alias="fieldType", default="text")
    options: list[HubSpotPropertyOption] = Field(default_factory=list)
    form_field: bool = Field(alias="formField", default=False)
    group_name: str = Field(alias="groupName", default="")
    description: str = ""
    calculated: bool = False
    modification_metadata: dict[str, Any] = Field(alias="modificationMetadata", default_factory=dict)


class HubSpotPropertiesResponse(BaseModel):
    results: list[HubSpotProperty]


class HubSpotUser(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str = ""
    email: str | None = ""
    first_name: str | None = Field(alias="firstName", default="")
    last_name: str | None = Field(alias="lastName", default="")


class HubSpotUsersResponse(BaseModel):
    results: list[HubSpotUser]


class HubSpotBootstrapResponse(BaseModel):
    """Single round-trip for deal form: pipelines + form-field properties + users.

    Aligns with FE note to bundle metadata when opening HubSpot flow.
    """

    model_config = ConfigDict(extra="forbid")

    pipelines: list[HubSpotPipeline]
    properties: list[HubSpotProperty]
    users: list[HubSpotUser]


# ── Deal search (US6 prep) ───────────────────────────────────────────────────

class HubSpotDealSearchResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    properties: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = Field(alias="createdAt", default=None)
    updated_at: str | None = Field(alias="updatedAt", default=None)
    archived: bool = False


class HubSpotDealSearchResponse(BaseModel):
    total: int = 0
    results: list[HubSpotDealSearchResult] = Field(default_factory=list)
    paging: dict[str, Any] | None = None
>>>>>>> origin/develop

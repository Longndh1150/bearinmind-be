"""HubSpot deal form payload (case 2: user fills form in chat, FE POSTs JSON to BE).

Aligns with `bearinmind-fe` `DealDraft` in `src/renderer/src/types/chat.ts`.
Validation is intentionally light (length bounds, enums); no separate validate endpoint.
"""

from __future__ import annotations

from typing import Literal

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
    """User-submitted deal draft from the in-chat form (case 2)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    deal_name: str | None = Field(default=None, alias="dealName", max_length=500)
    pipeline: str | None = Field(default=None, max_length=200)
    market: DealMarket | None = None
    jp_section_lead: str | None = Field(default=None, alias="jpSectionLead", max_length=200)
    status: DealStatus | None = None
    onsite_offshore_type: OnsiteOffshoreType | None = Field(default=None, alias="onsiteOffshoreType")
    onsite_unit_price: str | None = Field(default=None, alias="onsiteUnitPrice", max_length=200)
    offshore_unit_price: str | None = Field(default=None, alias="offshoreUnitPrice", max_length=200)
    onsite_delivery_team: list[str] | None = Field(
        default=None,
        alias="onsiteDeliveryTeam",
        max_length=50,
        description="At most 50 entries; each string trimmed by client.",
    )
    offshore_delivery_team: list[str] | None = Field(
        default=None,
        alias="offshoreDeliveryTeam",
        max_length=50,
    )
    year_of_pipeline: str | None = Field(default=None, alias="yearOfPipeline", max_length=50)
    owner: str | None = Field(default=None, max_length=200)
    deal_sub_owner: str | None = Field(default=None, alias="dealSubOwner", max_length=200)


class HubSpotDealCreateResponse(BaseModel):
    """Result after accepting draft (HubSpot create is stubbed until integration)."""

    model_config = ConfigDict(extra="forbid")

    success: bool = True
    hubspot_deal_id: str | None = Field(
        default=None,
        description="HubSpot deal id when integration succeeds.",
        examples=["123456789"],
    )
    message: str = Field(default="", examples=["Deal created (stub)"])

"""Case 2: user submits HubSpot deal form from chat (JSON body = HubSpotDealDraft)."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, status

from app.api.deps import require_active_user
from app.models.user import User
from app.schemas.hubspot_deal import HubSpotDealCreateResponse, HubSpotDealDraft

router = APIRouter(prefix="/hubspot", tags=["hubspot"])


@router.post(
    "/deals",
    response_model=HubSpotDealCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create HubSpot deal from form draft",
    description=(
        "Accepts the same JSON shape as the frontend `DealDraft` (camelCase keys). "
        "HubSpot integration can be wired later; this endpoint validates shape and returns a stub id."
    ),
)
async def create_deal_from_draft(
    draft: HubSpotDealDraft,
    _: User = Depends(require_active_user),
) -> HubSpotDealCreateResponse:
    # Stub: persist + real HubSpot call in Phase 2 (US5).
    _ = draft  # use fields when integrating
    return HubSpotDealCreateResponse(
        success=True,
        hubspot_deal_id=f"stub_{uuid4().hex[:12]}",
        message="Deal accepted (stub — HubSpot integration pending)",
    )

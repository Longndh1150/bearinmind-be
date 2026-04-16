"""HubSpot proxy endpoints — pipelines, properties, users, deal CRUD.

FE switches between ``direct`` (FE -> HubSpot) and ``backend`` (FE -> BE -> HubSpot)
via ``VITE_HUBSPOT_SOURCE``.  These routes serve the ``backend`` mode.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import require_active_user
from app.integrations.hubspot_client import HubSpotAPIError
from app.models.user import User
from app.schemas.hubspot_deal import (
    HubSpotBootstrapResponse,
    HubSpotDealCreateResponse,
    HubSpotDealDraft,
    HubSpotDealSearchResponse,
    HubSpotDealUpdateResponse,
    HubSpotPipelinesResponse,
    HubSpotPropertiesResponse,
    HubSpotUsersResponse,
)
from app.services import hubspot_service

from uuid import uuid4

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/hubspot", tags=["hubspot"])


# ── Metadata (read-only proxies) ─────────────────────────────────────────────


@router.get(
    "/pipelines",
    response_model=HubSpotPipelinesResponse,
    summary="Get deal pipelines from HubSpot",
)
async def get_pipelines(
    _: User = Depends(require_active_user),
) -> HubSpotPipelinesResponse:
    try:
        pipelines = await hubspot_service.fetch_pipelines()
    except HubSpotAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return HubSpotPipelinesResponse(results=pipelines)


@router.get(
    "/properties/deals",
    response_model=HubSpotPropertiesResponse,
    summary="Get deal property metadata from HubSpot",
)
async def get_deal_properties(
    form_field_only: bool = Query(
        False,
        description="If true, return only properties with formField=true (deal form fields).",
    ),
    _: User = Depends(require_active_user),
) -> HubSpotPropertiesResponse:
    try:
        props = await hubspot_service.fetch_deal_properties(form_field_only=form_field_only)
    except HubSpotAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return HubSpotPropertiesResponse(results=props)


@router.get(
    "/bootstrap",
    response_model=HubSpotBootstrapResponse,
    summary="Get pipelines + form-field properties + users (one round-trip)",
    description=(
        "Bundles the three metadata calls used to render the HubSpot deal form: "
        "pipelines, deal properties filtered to ``formField=true``, and users."
    ),
)
async def get_hubspot_bootstrap(
    _: User = Depends(require_active_user),
) -> HubSpotBootstrapResponse:
    try:
        pipelines, properties, users = await hubspot_service.fetch_bootstrap()
    except HubSpotAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return HubSpotBootstrapResponse(
        pipelines=pipelines,
        properties=properties,
        users=users,
    )


@router.get(
    "/users",
    response_model=HubSpotUsersResponse,
    summary="Get HubSpot users (for owner / sub-owner fields)",
)
async def get_users(
    _: User = Depends(require_active_user),
) -> HubSpotUsersResponse:
    try:
        users = await hubspot_service.fetch_users()
    except HubSpotAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return HubSpotUsersResponse(results=users)


# ── Deal CRUD ─────────────────────────────────────────────────────────────────


@router.post(
    "/deals",
    response_model=HubSpotDealCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a HubSpot deal from form draft",
    description=(
        "Accepts the same JSON shape as the frontend ``DealDraft`` (camelCase keys). "
        "Maps fields to HubSpot property names and creates the deal via the HubSpot API."
    ),
)
async def create_deal(
    draft: HubSpotDealDraft,
    _: User = Depends(require_active_user),
) -> HubSpotDealCreateResponse:
    result = await hubspot_service.create_deal(draft)
    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=result.message,
        )
    return result

@router.post(
    "/deals-list",
    response_model=HubSpotDealCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create HubSpot deal from list",
    description=(
        "Accepts a list of dictionaries. Returns a HubSpotDealCreateResponse."
    ),
)
async def create_deal_from_draft_list(
    payload: list[dict[str, str]],
    _: User = Depends(require_active_user),
) -> HubSpotDealCreateResponse:
    result = await hubspot_service.create_deal_from_list(payload)
    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=result.message,
        )
    return result

@router.patch(
    "/deals/{deal_id}",
    response_model=HubSpotDealUpdateResponse,
    summary="Update an existing HubSpot deal",
)
async def update_deal(
    deal_id: str,
    draft: HubSpotDealDraft,
    _: User = Depends(require_active_user),
) -> HubSpotDealUpdateResponse:
    result = await hubspot_service.update_deal(deal_id, draft)
    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=result.message,
        )
    return result


@router.get(
    "/deals/{deal_id}",
    summary="Get a single HubSpot deal by ID",
)
async def get_deal(
    deal_id: str,
    _: User = Depends(require_active_user),
) -> dict[str, Any]:
    try:
        result = await hubspot_service.get_deal(deal_id)
    except HubSpotAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    return result


@router.get(
    "/deals",
    response_model=HubSpotDealSearchResponse,
    summary="Search / list HubSpot deals (US6 prep)",
)
async def search_deals(
    limit: int = Query(20, ge=1, le=100),
    after: str | None = Query(None, description="Cursor for pagination"),
    dealstage: str | None = Query(None, description="Filter by deal stage"),
    pipeline: str | None = Query(None, description="Filter by pipeline ID"),
    _: User = Depends(require_active_user),
) -> HubSpotDealSearchResponse:
    filters: list[dict[str, Any]] = []
    if dealstage:
        filters.append({"propertyName": "dealstage", "operator": "EQ", "value": dealstage})
    if pipeline:
        filters.append({"propertyName": "pipeline", "operator": "EQ", "value": pipeline})

    return await hubspot_service.search_deals(
        filters=filters or None,
        properties=["dealname", "dealstage", "pipeline", "market", "closedate", "hubspot_owner_id", "amount"],
        limit=limit,
        after=after,
    )

"""Opportunity CRUD + CRM push — backed by PostgreSQL."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_active_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.common import Paginated
from app.schemas.opportunity import (
    OpportunityCreateRequest,
    OpportunityPublic,
    OpportunityPushCrmRequest,
    OpportunityPushCrmResult,
    OpportunityUpdateRequest,
)
from app.services import opportunity_service

router = APIRouter(prefix="/opportunities", tags=["opportunities"])


@router.post(
    "",
    response_model=OpportunityPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Create an opportunity (draft/unofficial supported)",
    description="US5: persist an opportunity captured from chat or manual entry.",
)
async def create_opportunity(
    payload: OpportunityCreateRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_active_user),
) -> OpportunityPublic:
    return await opportunity_service.create_opportunity(
        session, payload, user_id=user.id,
    )


@router.get(
    "",
    response_model=Paginated[OpportunityPublic],
    summary="List opportunities (multi-source later)",
    description="US6: returns a consolidated list; currently local DB.",
)
async def list_opportunities(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status_: str | None = Query(None, alias="status"),
    source: str | None = Query(None),
    q: str | None = Query(None, max_length=200),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_active_user),
) -> Paginated[OpportunityPublic]:
    items, total = await opportunity_service.list_opportunities(
        session, limit=limit, offset=offset, status=status_, source=source, q=q,
    )
    return Paginated(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/{opportunity_id}",
    response_model=OpportunityPublic,
    summary="Get opportunity by id",
)
async def get_opportunity(
    opportunity_id: UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_active_user),
) -> OpportunityPublic:
    result = await opportunity_service.get_opportunity(session, opportunity_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    return result


@router.put(
    "/{opportunity_id}",
    response_model=OpportunityPublic,
    summary="Update an opportunity",
)
async def update_opportunity(
    opportunity_id: UUID,
    payload: OpportunityUpdateRequest,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_active_user),
) -> OpportunityPublic:
    result = await opportunity_service.update_opportunity(session, opportunity_id, payload)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    return result


@router.put(
    "/{opportunity_id}/push-crm",
    response_model=OpportunityPushCrmResult,
    summary="Push an opportunity to CRM (HubSpot)",
    description="US5: requires explicit confirmation via request body.",
)
async def push_opportunity_to_crm(
    opportunity_id: UUID,
    payload: OpportunityPushCrmRequest,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_active_user),
) -> OpportunityPushCrmResult:
    if not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confirm=true is required to perform CRM write",
        )
    return await opportunity_service.push_to_crm(session, opportunity_id)

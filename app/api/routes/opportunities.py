<<<<<<< HEAD
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import require_active_user
from app.models.user import User
from app.schemas.common import Paginated, SourceRef
=======
"""Opportunity CRUD + CRM push — backed by PostgreSQL."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_active_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.common import Paginated
>>>>>>> origin/develop
from app.schemas.opportunity import (
    OpportunityCreateRequest,
    OpportunityPublic,
    OpportunityPushCrmRequest,
    OpportunityPushCrmResult,
    OpportunityUpdateRequest,
)
<<<<<<< HEAD
=======
from app.services import opportunity_service
>>>>>>> origin/develop

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
<<<<<<< HEAD
    _: User = Depends(require_active_user),
) -> OpportunityPublic:
    now = datetime.now(UTC)
    return OpportunityPublic(
        id=uuid4(),
        title=payload.title,
        description=payload.description,
        status="draft",
        source_ref=SourceRef(source=payload.source, external_id=None),
        is_official=False,
        pushed_at=None,
        client=payload.client,
        extracted=payload.extracted,
        created_at=now,
        updated_at=now,
=======
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_active_user),
) -> OpportunityPublic:
    return await opportunity_service.create_opportunity(
        session, payload, user_id=user.id,
>>>>>>> origin/develop
    )


@router.get(
    "",
    response_model=Paginated[OpportunityPublic],
    summary="List opportunities (multi-source later)",
<<<<<<< HEAD
    description="US6: returns a consolidated list; v1 can start with local DB only.",
=======
    description="US6: returns a consolidated list; currently local DB.",
>>>>>>> origin/develop
)
async def list_opportunities(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status_: str | None = Query(None, alias="status"),
    source: str | None = Query(None),
<<<<<<< HEAD
    unit_id: UUID | None = Query(None),
    q: str | None = Query(None, max_length=200),
    _: User = Depends(require_active_user),
) -> Paginated[OpportunityPublic]:
    # Stub dataset for FE mocking.
    now = datetime.now(UTC)
    item = OpportunityPublic(
        id=uuid4(),
        title="(stub) D365 for Japan retail",
        description="(stub) Implement D365 + Power Platform, timeline 3 months.",
        status="open",
        source_ref=SourceRef(source="chat"),
        is_official=False,
        pushed_at=None,
        client=None,
        extracted=None,
        created_at=now,
        updated_at=now,
    )
    return Paginated(items=[item], total=1, limit=limit, offset=offset)
=======
    q: str | None = Query(None, max_length=200),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_active_user),
) -> Paginated[OpportunityPublic]:
    items, total = await opportunity_service.list_opportunities(
        session, limit=limit, offset=offset, status=status_, source=source, q=q,
    )
    return Paginated(items=items, total=total, limit=limit, offset=offset)
>>>>>>> origin/develop


@router.get(
    "/{opportunity_id}",
    response_model=OpportunityPublic,
    summary="Get opportunity by id",
)
async def get_opportunity(
    opportunity_id: UUID,
<<<<<<< HEAD
    _: User = Depends(require_active_user),
) -> OpportunityPublic:
    now = datetime.now(UTC)
    return OpportunityPublic(
        id=opportunity_id,
        title="(stub) Opportunity detail",
        description="(stub) Details",
        status="draft",
        source_ref=SourceRef(source="chat"),
        is_official=False,
        pushed_at=None,
        client=None,
        extracted=None,
        created_at=now,
        updated_at=now,
    )
=======
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_active_user),
) -> OpportunityPublic:
    result = await opportunity_service.get_opportunity(session, opportunity_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    return result
>>>>>>> origin/develop


@router.put(
    "/{opportunity_id}",
    response_model=OpportunityPublic,
    summary="Update an opportunity",
)
async def update_opportunity(
    opportunity_id: UUID,
    payload: OpportunityUpdateRequest,
<<<<<<< HEAD
    _: User = Depends(require_active_user),
) -> OpportunityPublic:
    now = datetime.now(UTC)
    return OpportunityPublic(
        id=opportunity_id,
        title=payload.title or "(stub) Opportunity title",
        description=payload.description or "(stub) Opportunity description",
        status=payload.status or "draft",
        source_ref=SourceRef(source="chat"),
        is_official=False,
        pushed_at=None,
        client=payload.client,
        extracted=payload.extracted,
        created_at=now,
        updated_at=now,
    )
=======
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_active_user),
) -> OpportunityPublic:
    result = await opportunity_service.update_opportunity(session, opportunity_id, payload)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    return result
>>>>>>> origin/develop


@router.put(
    "/{opportunity_id}/push-crm",
    response_model=OpportunityPushCrmResult,
    summary="Push an opportunity to CRM (HubSpot)",
    description="US5: requires explicit confirmation via request body.",
)
async def push_opportunity_to_crm(
    opportunity_id: UUID,
    payload: OpportunityPushCrmRequest,
<<<<<<< HEAD
=======
    session: AsyncSession = Depends(get_session),
>>>>>>> origin/develop
    _: User = Depends(require_active_user),
) -> OpportunityPushCrmResult:
    if not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confirm=true is required to perform CRM write",
        )
<<<<<<< HEAD
    # Stub: return a fake HubSpot id.
    return OpportunityPushCrmResult(
        success=True,
        source="hubspot",
        external_id=f"deal_{opportunity_id}",
        message="(stub) Pushed to HubSpot",
    )

=======
    return await opportunity_service.push_to_crm(session, opportunity_id)
>>>>>>> origin/develop

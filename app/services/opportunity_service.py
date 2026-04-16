"""Opportunity persistence and CRM push service."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.opportunity import Opportunity
from app.schemas.common import SourceRef
from app.schemas.hubspot_deal import HubSpotDealDraft
from app.schemas.opportunity import (
    OpportunityCreateRequest,
    OpportunityExtracted,
    OpportunityParty,
    OpportunityPublic,
    OpportunityPushCrmResult,
    OpportunityUpdateRequest,
)
from app.services import hubspot_service

logger = logging.getLogger(__name__)


def _row_to_public(row: Opportunity) -> OpportunityPublic:
    client = None
    if row.client_info:
        try:
            client = OpportunityParty.model_validate(row.client_info)
        except Exception:
            pass

    extracted = None
    if row.extracted:
        try:
            extracted = OpportunityExtracted.model_validate(row.extracted)
        except Exception:
            pass

    return OpportunityPublic(
        id=row.id,
        title=row.title,
        description=row.description,
        status=row.status,  # type: ignore[arg-type]
        source_ref=SourceRef(
            source=row.source,  # type: ignore[arg-type]
            external_id=row.hubspot_deal_id,
        ),
        is_official=row.is_official,
        pushed_at=row.pushed_at,
        client=client,
        extracted=extracted,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def create_opportunity(
    session: AsyncSession,
    payload: OpportunityCreateRequest,
    *,
    user_id: UUID | None = None,
    conversation_id: UUID | None = None,
) -> OpportunityPublic:
    row = Opportunity(
        title=payload.title,
        description=payload.description,
        status="draft",
        source=payload.source,
        is_official=False,
        created_by_id=user_id,
        conversation_id=conversation_id,
        client_info=payload.client.model_dump(mode="json") if payload.client else None,
        extracted=payload.extracted.model_dump(mode="json") if payload.extracted else None,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _row_to_public(row)


async def get_opportunity(
    session: AsyncSession,
    opportunity_id: UUID,
) -> OpportunityPublic | None:
    row = await session.get(Opportunity, opportunity_id)
    if not row:
        return None
    return _row_to_public(row)


async def list_opportunities(
    session: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    source: str | None = None,
    q: str | None = None,
) -> tuple[list[OpportunityPublic], int]:
    base = select(Opportunity)
    count_q = select(func.count()).select_from(Opportunity)

    if status:
        base = base.where(Opportunity.status == status)
        count_q = count_q.where(Opportunity.status == status)
    if source:
        base = base.where(Opportunity.source == source)
        count_q = count_q.where(Opportunity.source == source)
    if q:
        pattern = f"%{q}%"
        base = base.where(Opportunity.title.ilike(pattern) | Opportunity.description.ilike(pattern))
        count_q = count_q.where(Opportunity.title.ilike(pattern) | Opportunity.description.ilike(pattern))

    total = (await session.execute(count_q)).scalar_one()
    rows = (
        await session.execute(
            base.order_by(Opportunity.created_at.desc()).offset(offset).limit(limit)
        )
    ).scalars().all()

    return [_row_to_public(r) for r in rows], total


async def update_opportunity(
    session: AsyncSession,
    opportunity_id: UUID,
    payload: OpportunityUpdateRequest,
) -> OpportunityPublic | None:
    row = await session.get(Opportunity, opportunity_id)
    if not row:
        return None

    if payload.title is not None:
        row.title = payload.title
    if payload.description is not None:
        row.description = payload.description
    if payload.status is not None:
        row.status = payload.status
    if payload.client is not None:
        row.client_info = payload.client.model_dump(mode="json")
    if payload.extracted is not None:
        row.extracted = payload.extracted.model_dump(mode="json")

    await session.commit()
    await session.refresh(row)
    return _row_to_public(row)


async def push_to_crm(
    session: AsyncSession,
    opportunity_id: UUID,
) -> OpportunityPushCrmResult:
    """Push an opportunity to HubSpot as a deal."""
    row = await session.get(Opportunity, opportunity_id)
    if not row:
        return OpportunityPushCrmResult(
            success=False,
            source="hubspot",
            external_id=None,
            message="Opportunity not found",
        )

    draft = HubSpotDealDraft(dealName=row.title)
    result = await hubspot_service.create_deal(draft)

    if result.success and result.hubspot_deal_id:
        row.hubspot_deal_id = result.hubspot_deal_id
        row.is_official = True
        row.pushed_at = datetime.now(UTC)
        row.source = "hubspot"
        await session.commit()
        await session.refresh(row)

        return OpportunityPushCrmResult(
            success=True,
            source="hubspot",
            external_id=result.hubspot_deal_id,
            message="Pushed to HubSpot",
        )

    return OpportunityPushCrmResult(
        success=False,
        source="hubspot",
        external_id=None,
        message=result.message,
    )

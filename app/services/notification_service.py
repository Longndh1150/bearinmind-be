"""Notification persistence/query service."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.schemas.notification import (
    NotificationCreateOpportunityMatchUnitRequest,
    NotificationPublic,
)


def _to_public(row: Notification) -> NotificationPublic:
    return NotificationPublic(
        id=row.id,
        type=row.type,
        fit_level=row.fit_level,
        is_read=row.is_read,
        read_at=row.read_at,
        opportunity_id=row.opportunity_id,
        unit_id=row.unit_id,
        title=row.title,
        message=row.message,
        payload=row.payload or {},
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def list_notifications(
    session: AsyncSession,
    *,
    user_id: UUID,
    limit: int = 50,
    offset: int = 0,
    unread_only: bool = False,
) -> tuple[list[NotificationPublic], int]:
    base_query = select(Notification).where(Notification.user_id == user_id)
    count_query = select(func.count()).select_from(Notification).where(Notification.user_id == user_id)

    if unread_only:
        base_query = base_query.where(Notification.is_read.is_(False))
        count_query = count_query.where(Notification.is_read.is_(False))

    total = (await session.execute(count_query)).scalar_one()
    rows = (
        await session.execute(
            base_query.order_by(Notification.created_at.desc()).offset(offset).limit(limit),
        )
    ).scalars().all()
    return [_to_public(r) for r in rows], total


async def mark_read_state(
    session: AsyncSession,
    *,
    notification_id: UUID,
    user_id: UUID,
    is_read: bool,
) -> NotificationPublic | None:
    result = await session.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        return None

    row.is_read = is_read
    row.read_at = datetime.now(UTC) if is_read else None
    await session.commit()
    await session.refresh(row)
    return _to_public(row)


async def create_opportunity_match_unit_notification(
    session: AsyncSession,
    payload: NotificationCreateOpportunityMatchUnitRequest,
) -> NotificationPublic:
    row = Notification(
        user_id=payload.recipient_user_id,
        type="opportunity_match_unit",
        opportunity_id=payload.opportunity_id,
        unit_id=payload.unit_id,
        fit_level=payload.fit_level,
        title=payload.title,
        message=payload.message,
        payload={
            "details": payload.details.model_dump(mode="json"),
        },
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _to_public(row)

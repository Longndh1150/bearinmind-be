from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_active_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.common import Paginated
from app.schemas.notification import (
    NotificationCreateOpportunityMatchUnitRequest,
    NotificationMarkReadRequest,
    NotificationPublic,
)
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get(
    "",
    response_model=Paginated[NotificationPublic],
    summary="List notifications (polling)",
    description="US2: FE polls this endpoint; later can evolve to push/stream.",
)
async def list_notifications(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    unread_only: bool = Query(False),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_active_user),
) -> Paginated[NotificationPublic]:
    items, total = await notification_service.list_notifications(
        session,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        unread_only=unread_only,
    )
    return Paginated(items=items, total=total, limit=limit, offset=offset)


@router.post(
    "/opportunity-match-unit",
    response_model=NotificationPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Create opportunity-match notification for Dlead",
    description=(
        "Creates a notification with flexible JSON payload for the "
        "opportunity-match-unit scenario."
    ),
)
async def create_opportunity_match_unit_notification(
    payload: NotificationCreateOpportunityMatchUnitRequest,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_active_user),
) -> NotificationPublic:
    return await notification_service.create_opportunity_match_unit_notification(session, payload)


@router.post(
    "/{notification_id}/read",
    response_model=NotificationPublic,
    summary="Mark a notification as read",
)
async def mark_read(
    notification_id: UUID,
    payload: NotificationMarkReadRequest | None = None,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_active_user),
) -> NotificationPublic:
    row = await notification_service.mark_read_state(
        session,
        notification_id=notification_id,
        user_id=current_user.id,
        is_read=True if payload is None else payload.is_read,
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return row


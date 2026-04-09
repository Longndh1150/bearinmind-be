from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query

from app.api.deps import require_active_user
from app.models.user import User
from app.schemas.common import Paginated
from app.schemas.notification import NotificationPublic

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
    _: User = Depends(require_active_user),
) -> Paginated[NotificationPublic]:
    now = datetime.now(UTC)
    item = NotificationPublic(
        id=uuid4(),
        type="opportunity_match",
        fit_level="high",
        is_read=False,
        read_at=None,
        opportunity_id=uuid4(),
        unit_id=uuid4(),
        title="(stub) Opportunity matches your unit",
        message="(stub) A new opportunity may fit your unit. Review and take action.",
        created_at=now,
        updated_at=now,
    )
    items = [item] if not unread_only else [item]
    return Paginated(items=items, total=len(items), limit=limit, offset=offset)


@router.post(
    "/{notification_id}/read",
    response_model=NotificationPublic,
    summary="Mark a notification as read",
)
async def mark_read(notification_id: UUID, _: User = Depends(require_active_user)) -> NotificationPublic:
    now = datetime.now(UTC)
    return NotificationPublic(
        id=notification_id,
        type="opportunity_match",
        fit_level="high",
        is_read=True,
        read_at=now,
        opportunity_id=uuid4(),
        unit_id=uuid4(),
        title="(stub) Marked as read",
        message="(stub) Notification marked as read.",
        created_at=now,
        updated_at=now,
    )


"""Unit tests for notification service."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, Mock
from uuid import uuid4

import pytest

from app.models.notification import Notification
from app.schemas.notification import (
    NotificationCreateOpportunityMatchUnitRequest,
    OpportunityMatchUnitNotificationDetails,
)
from app.services import notification_service


def _make_row(*, is_read: bool, title: str) -> MagicMock:
    row = MagicMock()
    row.id = uuid4()
    row.type = "opportunity_match_unit"
    row.fit_level = "high"
    row.is_read = is_read
    row.read_at = datetime(2026, 4, 16, tzinfo=UTC) if is_read else None
    row.opportunity_id = uuid4()
    row.unit_id = uuid4()
    row.title = title
    row.message = "message"
    row.payload = {
        "details": {
            "opportunity_name": "ABC",
            "required_tech": ["Java"],
        }
    }
    row.created_at = datetime(2026, 4, 16, tzinfo=UTC)
    row.updated_at = datetime(2026, 4, 16, tzinfo=UTC)
    return row


@pytest.mark.asyncio
async def test_list_notifications_returns_all_items():
    row_unread = _make_row(is_read=False, title="Unread item")
    row_read = _make_row(is_read=True, title="Read item")

    count_result = MagicMock()
    count_result.scalar_one.return_value = 2
    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = [row_unread, row_read]

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[count_result, list_result])

    items, total = await notification_service.list_notifications(
        session,
        user_id=uuid4(),
        limit=50,
        offset=0,
        unread_only=False,
    )

    assert total == 2
    assert len(items) == 2
    assert items[0].is_read is False
    assert items[1].is_read is True
    assert items[0].payload["details"]["opportunity_name"] == "ABC"


@pytest.mark.asyncio
async def test_create_opportunity_match_unit_notification():
    session = AsyncMock()
    session.add = Mock()

    async def refresh(row: Notification) -> None:
        row.id = uuid4()
        row.created_at = datetime(2026, 4, 16, tzinfo=UTC)
        row.updated_at = datetime(2026, 4, 16, tzinfo=UTC)
        row.is_read = False
        row.read_at = None

    session.refresh = AsyncMock(side_effect=refresh)

    payload = NotificationCreateOpportunityMatchUnitRequest(
        recipient_user_id=uuid4(),
        opportunity_id=uuid4(),
        unit_id=uuid4(),
        fit_level="high",
        title="Opportunity match for your unit",
        message="Co hoi phu hop, vui long lien he sales.",
        details=OpportunityMatchUnitNotificationDetails(
            opportunity_name="ABC",
            customer_group="JP",
            required_tech=["Java"],
            next_steps="Call customer",
            bear_message="Deadline gap, can check resource today?",
        ),
    )

    result = await notification_service.create_opportunity_match_unit_notification(session, payload)

    session.add.assert_called_once()
    added: Notification = session.add.call_args[0][0]
    assert added.type == "opportunity_match_unit"
    assert added.payload["details"]["opportunity_name"] == "ABC"
    assert result.fit_level == "high"
    assert result.payload["details"]["required_tech"] == ["Java"]


@pytest.mark.asyncio
async def test_mark_read_state_not_found():
    empty_result = MagicMock()
    empty_result.scalar_one_or_none.return_value = None

    session = AsyncMock()
    session.execute = AsyncMock(return_value=empty_result)

    out = await notification_service.mark_read_state(
        session,
        notification_id=uuid4(),
        user_id=uuid4(),
        is_read=True,
    )
    assert out is None


@pytest.mark.asyncio
async def test_mark_read_state_updates_read_flag():
    row = _make_row(is_read=False, title="Pending")
    result_wrapper = MagicMock()
    result_wrapper.scalar_one_or_none.return_value = row

    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_wrapper)

    out = await notification_service.mark_read_state(
        session,
        notification_id=row.id,
        user_id=uuid4(),
        is_read=True,
    )

    assert out is not None
    assert out.is_read is True
    assert out.read_at is not None
    session.commit.assert_awaited()

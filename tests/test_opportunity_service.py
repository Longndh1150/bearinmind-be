"""Unit tests for opportunity service — mocked async session + HubSpot."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest

from app.models.opportunity import Opportunity
from app.schemas.hubspot_deal import HubSpotDealCreateResponse
from app.schemas.opportunity import OpportunityCreateRequest, OpportunityUpdateRequest
from app.services import opportunity_service


@pytest.mark.asyncio
async def test_create_opportunity_adds_row_and_commits():
    # ``session.add`` is synchronous on AsyncSession — use ``Mock``, not ``AsyncMock``.
    session = AsyncMock()
    session.add = Mock()
    payload = OpportunityCreateRequest(title="New deal", description="Enough chars here")
    user_id = uuid4()
    conv_id = uuid4()

    async def refresh(row: Opportunity) -> None:
        if row.id is None:
            row.id = uuid4()
        row.created_at = datetime(2026, 3, 1, tzinfo=UTC)
        row.updated_at = datetime(2026, 3, 1, tzinfo=UTC)

    session.refresh = AsyncMock(side_effect=refresh)

    pub = await opportunity_service.create_opportunity(
        session, payload, user_id=user_id, conversation_id=conv_id
    )
    session.add.assert_called_once()
    added: Opportunity = session.add.call_args[0][0]
    assert isinstance(added, Opportunity)
    assert added.title == "New deal"
    assert added.created_by_id == user_id
    assert added.conversation_id == conv_id
    session.commit.assert_awaited()
    assert pub.title == "New deal"
    assert pub.id == added.id


@pytest.mark.asyncio
async def test_get_opportunity_none():
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    out = await opportunity_service.get_opportunity(session, uuid4())
    assert out is None


@pytest.mark.asyncio
async def test_get_opportunity_skips_invalid_client_json():
    """Invalid ``client_info`` JSON should not break the row; ``client`` becomes None."""
    oid = uuid4()
    row = MagicMock()
    row.id = oid
    row.title = "T"
    row.description = "D" * 10
    row.status = "draft"
    row.source = "chat"
    row.hubspot_deal_id = None
    row.is_official = False
    row.pushed_at = None
    row.client_info = {"not_a_party": True}
    row.extracted = None
    row.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    row.updated_at = datetime(2026, 1, 1, tzinfo=UTC)
    session = AsyncMock()
    session.get = AsyncMock(return_value=row)
    pub = await opportunity_service.get_opportunity(session, oid)
    assert pub is not None
    assert pub.client is None
    assert pub.title == "T"


@pytest.mark.asyncio
async def test_list_opportunities_returns_total_and_items():
    oid = uuid4()
    row = MagicMock()
    row.id = oid
    row.title = "Listed"
    row.description = "Desc" * 5
    row.status = "open"
    row.source = "chat"
    row.hubspot_deal_id = None
    row.is_official = False
    row.pushed_at = None
    row.client_info = None
    row.extracted = None
    row.created_at = datetime(2026, 1, 2, tzinfo=UTC)
    row.updated_at = datetime(2026, 1, 2, tzinfo=UTC)

    r_count = MagicMock()
    r_count.scalar_one.return_value = 1
    r_list = MagicMock()
    r_list.scalars.return_value.all.return_value = [row]
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[r_count, r_list])

    items, total = await opportunity_service.list_opportunities(session, limit=10, offset=0)
    assert total == 1
    assert len(items) == 1
    assert items[0].title == "Listed"


@pytest.mark.asyncio
async def test_update_opportunity_applies_fields():
    oid = uuid4()
    row = MagicMock()
    row.id = oid
    row.title = "Old"
    row.description = "Olddesc" * 3
    row.status = "draft"
    row.source = "chat"
    row.hubspot_deal_id = None
    row.is_official = False
    row.pushed_at = None
    row.client_info = None
    row.extracted = None
    row.created_at = datetime(2026, 1, 3, tzinfo=UTC)
    row.updated_at = datetime(2026, 1, 3, tzinfo=UTC)
    session = AsyncMock()
    session.get = AsyncMock(return_value=row)

    async def refresh(_row: MagicMock) -> None:
        _row.updated_at = datetime(2026, 1, 4, tzinfo=UTC)

    session.refresh = AsyncMock(side_effect=refresh)

    out = await opportunity_service.update_opportunity(
        session,
        oid,
        OpportunityUpdateRequest(title="NewTitle", status="open"),
    )
    assert out is not None
    assert row.title == "NewTitle"
    assert row.status == "open"
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_update_opportunity_none_when_missing():
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    out = await opportunity_service.update_opportunity(session, uuid4(), OpportunityUpdateRequest(title="N"))
    assert out is None


@pytest.mark.asyncio
async def test_push_to_crm_not_found():
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    out = await opportunity_service.push_to_crm(session, uuid4())
    assert out.success is False
    assert "not found" in out.message.lower()


@pytest.mark.asyncio
async def test_push_to_crm_success_updates_row():
    oid = uuid4()
    row = MagicMock()
    row.id = oid
    row.title = "CRM Title"
    session = AsyncMock()
    session.get = AsyncMock(return_value=row)
    ok = HubSpotDealCreateResponse(success=True, hubspot_deal_id="777", message="created")
    with patch(
        "app.services.opportunity_service.hubspot_service.create_deal",
        new_callable=AsyncMock,
        return_value=ok,
    ):
        out = await opportunity_service.push_to_crm(session, oid)
    assert out.success is True
    assert out.external_id == "777"
    assert row.hubspot_deal_id == "777"
    assert row.is_official is True
    assert row.source == "hubspot"
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_push_to_crm_hubspot_failure_no_commit_state_change():
    oid = uuid4()
    row = MagicMock()
    row.id = oid
    row.title = "Fail"
    row.hubspot_deal_id = None
    row.is_official = False
    row.source = "chat"
    session = AsyncMock()
    session.get = AsyncMock(return_value=row)
    bad = HubSpotDealCreateResponse(success=False, hubspot_deal_id=None, message="HubSpot error")
    with patch(
        "app.services.opportunity_service.hubspot_service.create_deal",
        new_callable=AsyncMock,
        return_value=bad,
    ):
        out = await opportunity_service.push_to_crm(session, oid)
    assert out.success is False
    assert out.external_id is None
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_push_to_crm_success_false_without_deal_id():
    """``success`` true but missing ``hubspot_deal_id`` should not commit."""
    oid = uuid4()
    row = MagicMock()
    row.id = oid
    row.title = "Weird"
    session = AsyncMock()
    session.get = AsyncMock(return_value=row)
    weird = HubSpotDealCreateResponse(success=True, hubspot_deal_id=None, message="odd")
    with patch(
        "app.services.opportunity_service.hubspot_service.create_deal",
        new_callable=AsyncMock,
        return_value=weird,
    ):
        out = await opportunity_service.push_to_crm(session, oid)
    assert out.success is False
    session.commit.assert_not_called()

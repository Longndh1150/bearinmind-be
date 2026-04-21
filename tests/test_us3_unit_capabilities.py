from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.schemas.context import ChatIntent, ConversationContext, DetectedLanguage
from app.services.unit_service import UnitService


def _ctx(
    *,
    clarify: str | None = None,
    payload: str | None = None,
    raw_message: str = "test",
) -> ConversationContext:
    return ConversationContext(
        intent=ChatIntent.update_capabilities,
        language=DetectedLanguage.vi,
        confidence=1.0,
        clarification_needed=clarify,
        opportunity_hint=payload,
        raw_message=raw_message,
    )


@pytest.mark.asyncio
async def test_us3_ask_for_clarification_returns_question():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()

    user = SimpleNamespace(email="lead@rikkeisoft.com")
    conv_id = uuid4()
    ctx = _ctx(clarify="Cho em xin tên chuyên gia và thêm tech stack ạ?")

    res = await UnitService.handle_update_capabilities(session, ctx, conv_id, "msg", user)

    assert "tên chuyên gia" in res.answer.lower()
    session.execute.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_us3_execute_update_dedup_tech_and_insert_new_experts():
    unit = SimpleNamespace(
        id=uuid4(),
        name="DN1",
        tech_stack=["Automation Test"],
        capabilities_updated_at=None,
    )
    unit_result = MagicMock()
    unit_result.scalars.return_value.first.return_value = unit

    experts_result = MagicMock()
    experts_result.scalars.return_value.all.return_value = []

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[unit_result, experts_result])
    session.add = MagicMock()
    session.commit = AsyncMock()

    user = SimpleNamespace(email="Lead@Rikkeisoft.com")
    payload = (
        '{"added_tech_stack":["Automation Test","Performance"," security "],'
        '"added_experts":["Lê Đức Thắng","lê đức thắng","Trần An"]}'
    )
    ctx = _ctx(payload=payload)

    res = await UnitService.handle_update_capabilities(session, ctx, uuid4(), "msg", user)

    assert res.conversation_id is not None
    assert set(unit.tech_stack) == {"Automation Test", "Performance", "security"}
    assert unit.capabilities_updated_at is not None
    assert session.add.call_count == 2  # "Lê Đức Thắng" + "Trần An"
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_us3_execute_update_merge_focus_for_existing_expert():
    unit = SimpleNamespace(
        id=uuid4(),
        name="DN1",
        tech_stack=["Automation Test"],
        capabilities_updated_at=None,
    )
    existing_expert = SimpleNamespace(name="Lê Đức Thắng", focus_areas=["Automation Test"])

    unit_result = MagicMock()
    unit_result.scalars.return_value.first.return_value = unit

    experts_result = MagicMock()
    experts_result.scalars.return_value.all.return_value = [existing_expert]

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[unit_result, experts_result])
    session.add = MagicMock()
    session.commit = AsyncMock()

    user = SimpleNamespace(email="lead@rikkeisoft.com")
    payload = '{"added_tech_stack":["Performance"],"added_experts":["Lê Đức Thắng"]}'
    ctx = _ctx(payload=payload)

    await UnitService.handle_update_capabilities(session, ctx, uuid4(), "msg", user)

    assert existing_expert.focus_areas == ["Automation Test", "Performance"]
    assert session.add.call_count == 0
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_us3_execute_update_accepts_string_payload_without_character_split():
    unit = SimpleNamespace(
        id=uuid4(),
        name="D5",
        code="D5",
        tech_stack=["Python"],
        capabilities_updated_at=None,
    )
    unit_result = MagicMock()
    unit_result.scalars.return_value.first.return_value = unit

    experts_result = MagicMock()
    experts_result.scalars.return_value.all.return_value = []

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[unit_result, experts_result])
    session.add = MagicMock()
    session.commit = AsyncMock()

    user = SimpleNamespace(email="minhln@rikkeisoft.com")
    payload = (
        '{"added_tech_stack":"Automation Test, Performance, Security",'
        '"added_experts":"Lê Đức Thắng"}'
    )
    ctx = _ctx(payload=payload, raw_message="D5")

    res = await UnitService.handle_update_capabilities(session, ctx, uuid4(), "D5", user)

    assert "thành công" in res.answer.lower()
    assert set(unit.tech_stack) == {"Python", "Automation Test", "Performance", "Security"}
    assert session.add.call_count == 1
    inserted_expert = session.add.call_args[0][0]
    assert inserted_expert.name == "Lê Đức Thắng"
    assert inserted_expert.focus_areas == ["Automation Test", "Performance", "Security"]
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_us3_execute_update_fallback_to_unit_code_when_email_not_matched():
    no_unit_by_email = MagicMock()
    no_unit_by_email.scalars.return_value.first.return_value = None

    unit = SimpleNamespace(
        id=uuid4(),
        name="DN1",
        code="DN1",
        tech_stack=["Automation Test"],
        capabilities_updated_at=None,
    )
    unit_by_code_result = MagicMock()
    unit_by_code_result.scalars.return_value.first.return_value = unit

    experts_result = MagicMock()
    experts_result.scalars.return_value.all.return_value = []

    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[no_unit_by_email, unit_by_code_result, experts_result]
    )
    session.add = MagicMock()
    session.commit = AsyncMock()

    user = SimpleNamespace(email="unknown@rikkeisoft.com")
    payload = '{"added_tech_stack":["Performance"],"added_experts":["Lê Đức Thắng"]}'
    ctx = _ctx(payload=payload, raw_message="Cập nhật giúp em cho đơn vị DN1")

    res = await UnitService.handle_update_capabilities(
        session, ctx, uuid4(), "Cập nhật DN1", user
    )

    assert "thành công" in res.answer.lower()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_us3_execute_update_no_unit_mapping_asks_unit_code():
    no_unit_by_email = MagicMock()
    no_unit_by_email.scalars.return_value.first.return_value = None

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[no_unit_by_email])
    session.add = MagicMock()
    session.commit = AsyncMock()

    user = SimpleNamespace(email="unknown@rikkeisoft.com")
    payload = '{"added_tech_stack":["Performance"],"added_experts":["Lê Đức Thắng"]}'
    ctx = _ctx(payload=payload, raw_message="Cập nhật năng lực giúp em")

    res = await UnitService.handle_update_capabilities(
        session, ctx, uuid4(), "Cập nhật năng lực", user
    )

    assert "mã đơn vị" in res.answer.lower()
    session.commit.assert_not_awaited()

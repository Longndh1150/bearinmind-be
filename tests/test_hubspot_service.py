"""Unit tests for HubSpot service — mapping, normalization, humanize (no network)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.hubspot_deal import HubSpotDealDraft, HubSpotProperty, HubSpotPropertyOption
from app.services.hubspot_service import (
    draft_to_hubspot_properties,
    humanize_deal_properties,
    resolve_property_display,
)


def test_draft_to_hubspot_maps_core_fields():
    draft = HubSpotDealDraft(
        dealName="ACME D365",
        pipeline="26RKJP Pipeline",
        market="JP",
        status="D",
        owner="90617141",
        dealSubOwner="90821048",
    )
    props = draft_to_hubspot_properties(draft)
    by_name = {p["name"]: p["value"] for p in props}
    assert by_name["dealname"] == "ACME D365"
    assert by_name["pipeline"] == "26RKJP Pipeline"
    assert by_name["market"] == "JP"
    assert by_name["dealstage"] == "D"
    assert by_name["hubspot_owner_id"] == "90617141"
    assert by_name["deal_sub_owner"] == "90821048"


def test_draft_multiselect_lists_join_with_semicolon():
    draft = HubSpotDealDraft(
        dealName="X",
        thSectionLead=["th_lead_a", "th_lead_b"],
        onsiteDeliveryTeam=["AD", "ES"],
    )
    props = draft_to_hubspot_properties(draft)
    by_name = {p["name"]: p["value"] for p in props}
    assert by_name["th_section_lead"] == "th_lead_a;th_lead_b"
    assert by_name["onsitedeliveryteam"] == "AD;ES"


def test_draft_extra_hubspot_key_pass_through():
    """Unknown keys (HubSpot internal names sent by client) pass through as property names."""
    draft = HubSpotDealDraft.model_validate(
        {
            "dealName": "Extra",
            "tech_stack": "kotlin;dot_net",  # extra key → pass-through branch
        }
    )
    props = draft_to_hubspot_properties(draft)
    by_name = {p["name"]: p["value"] for p in props}
    assert by_name["dealname"] == "Extra"
    assert by_name["tech_stack"] == "kotlin;dot_net"


def test_draft_omits_none_and_empty():
    draft = HubSpotDealDraft(dealName="Only name")
    props = draft_to_hubspot_properties(draft)
    names = {p["name"] for p in props}
    assert "market" not in names
    assert "dealname" in names


def test_resolve_property_display_unknown_property():
    idx: dict = {}
    label, val = resolve_property_display("unknown_prop", "x", idx)
    assert label == "unknown_prop"
    assert val == "x"


def test_resolve_property_display_no_options():
    prop = HubSpotProperty(name="amount", label="Amount", type="number", fieldType="number", options=[])
    idx = {"amount": prop}
    label, val = resolve_property_display("amount", "12345", idx)
    assert label == "Amount"
    assert val == "12345"


def test_resolve_property_display_enumeration_single():
    prop = HubSpotProperty(
        name="market",
        label="Market",
        type="enumeration",
        fieldType="select",
        options=[
            HubSpotPropertyOption(label="Japan", value="JP", displayOrder=0, hidden=False),
            HubSpotPropertyOption(label="US", value="US", displayOrder=1, hidden=False),
        ],
    )
    idx = {"market": prop}
    label, val = resolve_property_display("market", "JP", idx)
    assert label == "Market"
    assert val == "Japan"


def test_resolve_property_display_multiselect_semicolon():
    prop = HubSpotProperty(
        name="onsitedeliveryteam",
        label="Onsite team",
        type="enumeration",
        fieldType="checkbox",
        options=[
            HubSpotPropertyOption(label="Team AD", value="AD", displayOrder=0, hidden=False),
            HubSpotPropertyOption(label="Team ES", value="ES", displayOrder=1, hidden=False),
        ],
    )
    idx = {"onsitedeliveryteam": prop}
    label, val = resolve_property_display("onsitedeliveryteam", "AD;ES", idx)
    assert label == "Onsite team"
    assert val == "Team AD; Team ES"


@pytest.mark.asyncio
async def test_humanize_deal_properties_uses_property_index():
    fake_props = [
        HubSpotProperty(
            name="market",
            label="Market",
            type="enumeration",
            fieldType="select",
            options=[HubSpotPropertyOption(label="Japan", value="JP", displayOrder=0, hidden=False)],
        )
    ]

    async def fake_fetch(*_a, **_k):
        return fake_props

    with patch("app.services.hubspot_service.fetch_deal_properties", side_effect=fake_fetch):
        out = await humanize_deal_properties({"market": "JP", "unknown": "raw"})
    assert out["Market"] == "Japan"
    assert out["unknown"] == "raw"


@pytest.mark.asyncio
async def test_create_deal_maps_hubspot_error_to_response():
    from app.services import hubspot_service as hs

    with patch("app.services.hubspot_service.hubspot_client.create_deal", new_callable=AsyncMock) as m:
        from app.integrations.hubspot_client import HubSpotAPIError

        m.side_effect = HubSpotAPIError(403, "FORBIDDEN", "scope missing")
        result = await hs.create_deal(HubSpotDealDraft(dealName="x"))
    assert result.success is False
    assert result.hubspot_deal_id is None
    assert "HubSpot error" in result.message


@pytest.mark.asyncio
async def test_create_deal_success_parses_deal_id():
    from app.services import hubspot_service as hs

    with patch("app.services.hubspot_service.hubspot_client.create_deal", new_callable=AsyncMock) as m:
        m.return_value = {"dealId": 999888777}
        result = await hs.create_deal(HubSpotDealDraft(dealName="Win"))
    assert result.success is True
    assert result.hubspot_deal_id == "999888777"


@pytest.mark.asyncio
async def test_search_deals_returns_empty_on_hubspot_error():
    from app.integrations.hubspot_client import HubSpotAPIError
    from app.services import hubspot_service as hs

    with patch("app.services.hubspot_service.hubspot_client.search_deals", new_callable=AsyncMock) as m:
        m.side_effect = HubSpotAPIError(400, "BAD", "bad")
        out = await hs.search_deals(filters=None, limit=5)
    assert out.total == 0
    assert out.results == []


@pytest.mark.asyncio
async def test_fetch_deal_properties_form_field_filter():
    raw = {
        "results": [
            {
                "name": "on_form",
                "label": "On",
                "type": "string",
                "fieldType": "text",
                "formField": True,
                "options": [],
            },
            {
                "name": "off_form",
                "label": "Off",
                "type": "string",
                "fieldType": "text",
                "formField": False,
                "options": [],
            },
        ]
    }
    with patch("app.services.hubspot_service.hubspot_client.get_properties", new_callable=AsyncMock, return_value=raw):
        from app.services import hubspot_service as hs

        all_p = await hs.fetch_deal_properties(form_field_only=False)
        ff = await hs.fetch_deal_properties(form_field_only=True)
    assert len(all_p) == 2
    assert len(ff) == 1
    assert ff[0].name == "on_form"


@pytest.mark.asyncio
async def test_fetch_pipelines_accepts_list_or_results_wrapper():
    from app.services import hubspot_service as hs

    pl_raw = {
        "pipelineId": "x",
        "label": "XL",
        "displayOrder": 0,
        "active": True,
        "stages": [{"stageId": "s1", "label": "S", "displayOrder": 0, "active": True}],
    }
    with patch("app.services.hubspot_service.hubspot_client.get_pipelines", new_callable=AsyncMock, return_value=[pl_raw]):
        out_list = await hs.fetch_pipelines()
    assert len(out_list) == 1
    assert out_list[0].id == "x"
    assert out_list[0].stages[0].id == "s1"

    with patch(
        "app.services.hubspot_service.hubspot_client.get_pipelines",
        new_callable=AsyncMock,
        return_value={"results": [pl_raw]},
    ):
        out_wrapped = await hs.fetch_pipelines()
    assert len(out_wrapped) == 1


@pytest.mark.asyncio
async def test_update_deal_failure_returns_response():
    from app.services import hubspot_service as hs

    with patch("app.services.hubspot_service.hubspot_client.update_deal", new_callable=AsyncMock) as m:
        from app.integrations.hubspot_client import HubSpotAPIError

        m.side_effect = HubSpotAPIError(400, "VALIDATION", "bad")
        out = await hs.update_deal("99", HubSpotDealDraft(dealName="x"))
    assert out.success is False
    assert "HubSpot error" in out.message


@pytest.mark.asyncio
async def test_get_deal_returns_none_on_hubspot_error():
    from app.services import hubspot_service as hs

    with patch("app.services.hubspot_service.hubspot_client.get_deal", new_callable=AsyncMock) as m:
        from app.integrations.hubspot_client import HubSpotAPIError

        m.side_effect = HubSpotAPIError(404, "NOT_FOUND", "gone")
        out = await hs.get_deal("1")
    assert out is None


@pytest.mark.asyncio
async def test_fetch_bootstrap_runs_three_fetches():
    from app.schemas.hubspot_deal import HubSpotPipeline, HubSpotUser
    from app.services import hubspot_service as hs

    pl = [
        HubSpotPipeline(
            pipelineId="p1",
            label="P1",
            displayOrder=0,
            archived=False,
            stages=[],
        )
    ]
    props = [
        HubSpotProperty(
            name="dealname",
            label="Name",
            type="string",
            fieldType="text",
            formField=True,
        )
    ]
    users = [HubSpotUser(id="1", email="a@b.com", firstName="A", lastName="B")]

    with (
        patch("app.services.hubspot_service.fetch_pipelines", new_callable=AsyncMock, return_value=pl),
        patch(
            "app.services.hubspot_service.fetch_deal_properties",
            new_callable=AsyncMock,
            return_value=props,
        ),
        patch("app.services.hubspot_service.fetch_users", new_callable=AsyncMock, return_value=users),
    ):
        p, pr, u = await hs.fetch_bootstrap()

    assert len(p) == 1 and p[0].id == "p1"
    assert len(pr) == 1 and pr[0].name == "dealname"
    assert len(u) == 1 and u[0].id == "1"

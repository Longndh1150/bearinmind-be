"""API tests for HubSpot routes — auth override + mocked service."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import require_active_user
from app.integrations.hubspot_client import HubSpotAPIError
from app.main import app
from app.schemas.hubspot_deal import (
    HubSpotBootstrapResponse,
    HubSpotDealCreateResponse,
    HubSpotPipeline,
    HubSpotProperty,
    HubSpotUser,
)


@pytest.fixture
def client_authed(fake_user):
    app.dependency_overrides[require_active_user] = lambda: fake_user
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_get_pipelines_returns_results(client_authed: TestClient):
    pl = [
        HubSpotPipeline(
            pipelineId="pid",
            label="L",
            displayOrder=0,
            archived=False,
            stages=[],
        )
    ]
    with patch("app.api.routes.hubspot.hubspot_service.fetch_pipelines", new_callable=AsyncMock, return_value=pl):
        r = client_authed.get("/api/v1/hubspot/pipelines")
    assert r.status_code == 200
    data = r.json()
    assert "results" in data
    assert len(data["results"]) == 1
    assert data["results"][0]["pipelineId"] == "pid"


def test_get_properties_form_field_only_query(client_authed: TestClient):
    props = [
        HubSpotProperty(
            name="dealname",
            label="Deal",
            type="string",
            fieldType="text",
            formField=True,
        ),
        HubSpotProperty(
            name="hs_internal",
            label="Internal",
            type="string",
            fieldType="text",
            formField=False,
        ),
    ]
    captured: dict = {}

    async def fetch_side_effect(*_a, form_field_only: bool = False, **_k):
        captured["form_field_only"] = form_field_only
        return props if not form_field_only else [props[0]]

    with patch(
        "app.api.routes.hubspot.hubspot_service.fetch_deal_properties",
        new_callable=AsyncMock,
        side_effect=fetch_side_effect,
    ):
        r_all = client_authed.get("/api/v1/hubspot/properties/deals")
        r_ff = client_authed.get("/api/v1/hubspot/properties/deals?form_field_only=true")
    assert r_all.status_code == 200
    assert len(r_all.json()["results"]) == 2
    assert r_ff.status_code == 200
    assert len(r_ff.json()["results"]) == 1
    assert captured.get("form_field_only") is True


def test_bootstrap_returns_three_buckets(client_authed: TestClient):
    boot = HubSpotBootstrapResponse(
        pipelines=[
            HubSpotPipeline(
                pipelineId="p",
                label="P",
                displayOrder=0,
                archived=False,
                stages=[],
            )
        ],
        properties=[
            HubSpotProperty(
                name="dealname",
                label="N",
                type="string",
                fieldType="text",
                formField=True,
            )
        ],
        users=[HubSpotUser(id="1", email="e@e.com", firstName="E", lastName="E")],
    )
    with patch(
        "app.api.routes.hubspot.hubspot_service.fetch_bootstrap",
        new_callable=AsyncMock,
        return_value=(boot.pipelines, boot.properties, boot.users),
    ):
        r = client_authed.get("/api/v1/hubspot/bootstrap")
    assert r.status_code == 200
    j = r.json()
    assert len(j["pipelines"]) == 1
    assert len(j["properties"]) == 1
    assert len(j["users"]) == 1


def test_create_deal_502_when_hubspot_fails(client_authed: TestClient):
    bad = HubSpotDealCreateResponse(success=False, hubspot_deal_id=None, message="HubSpot down")
    with patch("app.api.routes.hubspot.hubspot_service.create_deal", new_callable=AsyncMock, return_value=bad):
        r = client_authed.post("/api/v1/hubspot/deals", json={"dealName": "X"})
    assert r.status_code == 502
    assert "HubSpot down" in r.json()["detail"]


def test_create_deal_201_on_success(client_authed: TestClient):
    ok = HubSpotDealCreateResponse(success=True, hubspot_deal_id="123", message="ok")
    with patch("app.api.routes.hubspot.hubspot_service.create_deal", new_callable=AsyncMock, return_value=ok):
        r = client_authed.post("/api/v1/hubspot/deals", json={"dealName": "Win"})
    assert r.status_code == 201
    assert r.json()["hubspot_deal_id"] == "123"


def test_hubspot_routes_require_auth_when_no_override():
    c = TestClient(app)
    r = c.get("/api/v1/hubspot/pipelines")
    assert r.status_code == 401


def test_get_pipelines_propagates_hubspot_api_error_status(client_authed: TestClient):
    with patch(
        "app.api.routes.hubspot.hubspot_service.fetch_pipelines",
        new_callable=AsyncMock,
        side_effect=HubSpotAPIError(401, "UNAUTHORIZED", "invalid token"),
    ):
        r = client_authed.get("/api/v1/hubspot/pipelines")
    assert r.status_code == 401
    assert "invalid token" in r.json()["detail"]


def test_get_deal_404_when_service_returns_none(client_authed: TestClient):
    with patch("app.api.routes.hubspot.hubspot_service.get_deal", new_callable=AsyncMock, return_value=None):
        r = client_authed.get("/api/v1/hubspot/deals/123")
    assert r.status_code == 404


def test_get_deal_returns_json(client_authed: TestClient):
    payload = {"id": "123", "properties": {"dealname": "X"}}
    with patch("app.api.routes.hubspot.hubspot_service.get_deal", new_callable=AsyncMock, return_value=payload):
        r = client_authed.get("/api/v1/hubspot/deals/123")
    assert r.status_code == 200
    assert r.json()["id"] == "123"


def test_patch_deal_502_on_failure(client_authed: TestClient):
    from app.schemas.hubspot_deal import HubSpotDealUpdateResponse

    bad = HubSpotDealUpdateResponse(success=False, hubspot_deal_id="1", message="fail")
    with patch("app.api.routes.hubspot.hubspot_service.update_deal", new_callable=AsyncMock, return_value=bad):
        r = client_authed.patch("/api/v1/hubspot/deals/1", json={"dealName": "Z"})
    assert r.status_code == 502


def test_search_deals_ok(client_authed: TestClient):
    from app.schemas.hubspot_deal import HubSpotDealSearchResponse

    empty = HubSpotDealSearchResponse(total=0, results=[], paging=None)
    with patch("app.api.routes.hubspot.hubspot_service.search_deals", new_callable=AsyncMock, return_value=empty):
        r = client_authed.get("/api/v1/hubspot/deals")
    assert r.status_code == 200
    assert r.json()["total"] == 0

"""Tests for dev-only smoke endpoints (LLM + HubSpot key checks)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.routes.dev import DevSmokeResult
from app.main import app


@pytest.fixture
def dev_settings(monkeypatch: pytest.MonkeyPatch):
    """Non-production env + isolated settings object for dev routes."""

    s = SimpleNamespace(
        app_env="development",
        llm_api_key="test-llm-key",
        llm_base_url="",
        llm_model_secondary="test-model",
        hubspot_api_key="pat-test",
    )
    monkeypatch.setattr("app.api.routes.dev.settings", s)
    return s


def test_smoke_llm_missing_key_returns_ok_false(dev_settings):
    dev_settings.llm_api_key = ""
    r = TestClient(app).get("/api/v1/dev/smoke/llm")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "LLM_API_KEY" in body["message"]


def test_smoke_hubspot_missing_key_returns_ok_false(dev_settings):
    dev_settings.hubspot_api_key = ""
    r = TestClient(app).get("/api/v1/dev/smoke/hubspot")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "HUBSPOT_API_KEY" in body["message"]


def test_smoke_llm_success_patched(dev_settings):
    ok = DevSmokeResult(ok=True, message="LLM API key works.", detail="model='test-model', reply='ok'")
    with patch("app.api.routes.dev.asyncio.to_thread", new_callable=AsyncMock, return_value=ok):
        r = TestClient(app).get("/api/v1/dev/smoke/llm")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_smoke_hubspot_success_patched(dev_settings):
    from app.schemas.hubspot_deal import HubSpotUser

    users = [HubSpotUser(id="1", email="a@b.com", firstName="A", lastName="B")]
    with patch("app.api.routes.dev.hubspot_service.fetch_users", new_callable=AsyncMock, return_value=users):
        r = TestClient(app).get("/api/v1/dev/smoke/hubspot")
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True
    assert "users_fetched=1" in (j.get("detail") or "")


def test_smoke_hubspot_hub_spot_api_error(dev_settings):
    from app.integrations.hubspot_client import HubSpotAPIError

    with patch(
        "app.api.routes.dev.hubspot_service.fetch_users",
        new_callable=AsyncMock,
        side_effect=HubSpotAPIError(403, "FORBIDDEN", "scope"),
    ):
        r = TestClient(app).get("/api/v1/dev/smoke/hubspot")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "HubSpot" in body["message"]


def test_smoke_endpoints_forbidden_in_production(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.api.routes.dev.settings", SimpleNamespace(app_env="production"))
    c = TestClient(app)
    assert c.get("/api/v1/dev/smoke/llm").status_code == 403
    assert c.get("/api/v1/dev/smoke/hubspot").status_code == 403

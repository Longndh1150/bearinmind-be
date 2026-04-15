"""Unit tests for HubSpot HTTP client — mocked transport, retries, errors."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.integrations.hubspot_client import HubSpotAPIError, _request, get_users


def _fake_build_factory_shared(responses: list[httpx.Response]):
    """Shared response index across retries (each retry opens a new ``AsyncClient``)."""

    state: dict[str, int] = {"i": 0}

    class _FakeClient:
        async def __aenter__(self) -> _FakeClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def request(self, *args: object, **kwargs: object) -> httpx.Response:
            i = state["i"]
            state["i"] += 1
            if i >= len(responses):
                return responses[-1]
            return responses[i]

    def _build() -> _FakeClient:
        return _FakeClient()

    return _build


@pytest.mark.asyncio
async def test_get_users_success_json(monkeypatch: pytest.MonkeyPatch):
    body = {"results": [{"id": "1", "email": "a@b.com"}]}
    monkeypatch.setattr(
        "app.integrations.hubspot_client._build_client",
        _fake_build_factory_shared([httpx.Response(200, json=body)]),
    )
    out = await get_users()
    assert out == body


@pytest.mark.asyncio
async def test_request_raises_hub_spot_api_error_on_400(monkeypatch: pytest.MonkeyPatch):
    err = {"category": "VALIDATION_ERROR", "message": "bad field", "correlationId": "abc"}
    monkeypatch.setattr(
        "app.integrations.hubspot_client._build_client",
        _fake_build_factory_shared([httpx.Response(400, json=err)]),
    )
    with pytest.raises(HubSpotAPIError) as ei:
        await _request("GET", "/settings/v3/users")
    assert ei.value.status_code == 400
    assert ei.value.category == "VALIDATION_ERROR"
    assert ei.value.correlation_id == "abc"
    assert "bad field" in str(ei.value)


@pytest.mark.asyncio
async def test_request_retries_429_then_succeeds(monkeypatch: pytest.MonkeyPatch):
    ok = {"results": []}
    monkeypatch.setattr(
        "app.integrations.hubspot_client._build_client",
        _fake_build_factory_shared(
            [
                httpx.Response(429, text="slow down"),
                httpx.Response(200, json=ok),
            ]
        ),
    )
    with patch("app.integrations.hubspot_client.asyncio.sleep", new=AsyncMock()):
        out = await get_users()
    assert out == ok


@pytest.mark.asyncio
async def test_request_exhausts_retries_on_500(monkeypatch: pytest.MonkeyPatch):
    # HubSpot error bodies are JSON; plain text breaks ``resp.json()`` on the final attempt.
    err_json = {"category": "SERVER_ERROR", "message": "internal"}
    monkeypatch.setattr(
        "app.integrations.hubspot_client._build_client",
        _fake_build_factory_shared(
            [
                httpx.Response(500, json=err_json),
                httpx.Response(500, json=err_json),
                httpx.Response(500, json=err_json),
            ]
        ),
    )
    with patch("app.integrations.hubspot_client.asyncio.sleep", new=AsyncMock()):
        with pytest.raises(HubSpotAPIError) as ei:
            await get_users()
    assert ei.value.status_code == 500


@pytest.mark.asyncio
async def test_request_non_json_error_body_still_raises(monkeypatch: pytest.MonkeyPatch):
    """Non-JSON error bodies must not crash ``_request`` (plain-text 502)."""
    monkeypatch.setattr(
        "app.integrations.hubspot_client._build_client",
        _fake_build_factory_shared([httpx.Response(502, text="bad gateway")]),
    )
    with pytest.raises(HubSpotAPIError) as ei:
        await get_users()
    assert ei.value.status_code == 502


@pytest.mark.asyncio
async def test_request_retries_on_connect_error(monkeypatch: pytest.MonkeyPatch):
    state = {"n": 0}

    class _Client:
        async def __aenter__(self) -> _Client:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def request(self, *args: object, **kwargs: object) -> httpx.Response:
            state["n"] += 1
            if state["n"] == 1:
                raise httpx.ConnectError("connection refused")
            return httpx.Response(200, json={"results": []})

    monkeypatch.setattr("app.integrations.hubspot_client._build_client", lambda: _Client())
    with patch("app.integrations.hubspot_client.asyncio.sleep", new=AsyncMock()):
        out = await get_users()
    assert out == {"results": []}

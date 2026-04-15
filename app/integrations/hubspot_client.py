"""Thin async HTTP client for HubSpot APIs.

Uses:
- Legacy v1 for deal create (``POST /deals/v1/deal/``) — aligned with FE direct mode.
- v3 endpoints for metadata (properties, users) and CRM object operations.
- v1 pipelines endpoint (``GET /crm-pipelines/v1/pipelines/{objectType}``).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BACKOFF_BASE = 0.5  # seconds
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class HubSpotAPIError(Exception):
    """Raised when HubSpot returns a non-success response."""

    def __init__(self, status_code: int, category: str, message: str, correlation_id: str | None = None):
        self.status_code = status_code
        self.category = category
        self.correlation_id = correlation_id
        super().__init__(message)


def _build_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.hubspot_base_url.rstrip("/"),
        headers={
            "Authorization": f"Bearer {settings.hubspot_api_key}",
            "Content-Type": "application/json",
        },
        timeout=httpx.Timeout(connect=5.0, read=15.0, write=10.0, pool=5.0),
    )


async def _request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: Any | None = None,
) -> Any:
    """Execute an HTTP request with retry + exponential backoff."""

    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        async with _build_client() as client:
            try:
                resp = await client.request(method, path, params=params, json=json_body)
            except httpx.TransportError as exc:
                last_exc = exc
                wait = _BACKOFF_BASE * (2**attempt)
                logger.warning("HubSpot transport error (attempt %d): %s — retrying in %.1fs", attempt + 1, exc, wait)
                await asyncio.sleep(wait)
                continue

            if resp.status_code < 400:
                return resp.json() if resp.content else None

            if resp.status_code in _RETRYABLE_STATUS_CODES and attempt < _MAX_RETRIES - 1:
                wait = _BACKOFF_BASE * (2**attempt)
                logger.warning("HubSpot %s (attempt %d) — retrying in %.1fs", resp.status_code, attempt + 1, wait)
                await asyncio.sleep(wait)
                last_exc = HubSpotAPIError(resp.status_code, "RETRYABLE", resp.text)
                continue

            try:
                body = resp.json() if resp.content else {}
            except Exception:
                body = {}
            raise HubSpotAPIError(
                status_code=resp.status_code,
                category=body.get("category", "UNKNOWN"),
                message=body.get("message", resp.text),
                correlation_id=body.get("correlationId"),
            )

    raise last_exc or HubSpotAPIError(500, "RETRY_EXHAUSTED", "Max retries exceeded")


# ── Pipelines (legacy v1) ────────────────────────────────────────────────────

async def get_pipelines(object_type: str = "deals") -> Any:
    """GET /crm-pipelines/v1/pipelines/{objectType}"""
    return await _request(
        "GET",
        f"/crm-pipelines/v1/pipelines/{object_type}",
        params={"includeInactive": "EXCLUDE_DELETED"},
    )


# ── Properties (v3) ──────────────────────────────────────────────────────────

async def get_properties(object_type: str = "deals") -> Any:
    """GET /crm/v3/properties/{objectType}"""
    return await _request(
        "GET",
        f"/crm/v3/properties/{object_type}",
        params={"dataSensitivity": "non_sensitive"},
    )


# ── Users (v3 settings) ──────────────────────────────────────────────────────

async def get_users() -> Any:
    """GET /settings/v3/users"""
    return await _request("GET", "/settings/v3/users")


# ── Deals ─────────────────────────────────────────────────────────────────────

async def create_deal(properties: list[dict[str, str]]) -> Any:
    """POST /deals/v1/deal/ (legacy v1 — aligned with FE direct mode)."""
    return await _request(
        "POST",
        "/deals/v1/deal/",
        json_body={"properties": properties},
    )


async def update_deal(deal_id: str, properties: list[dict[str, str]]) -> Any:
    """PATCH /crm/v3/objects/deals/{dealId} (v3 — property key/value object)."""
    props_obj = {p["name"]: p["value"] for p in properties}
    return await _request(
        "PATCH",
        f"/crm/v3/objects/deals/{deal_id}",
        json_body={"properties": props_obj},
    )


async def get_deal(deal_id: str, properties: list[str] | None = None) -> Any:
    """GET /crm/v3/objects/deals/{dealId}"""
    params: dict[str, Any] = {}
    if properties:
        params["properties"] = ",".join(properties)
    return await _request("GET", f"/crm/v3/objects/deals/{deal_id}", params=params)


async def search_deals(
    *,
    filters: list[dict[str, Any]] | None = None,
    sorts: list[dict[str, str]] | None = None,
    properties: list[str] | None = None,
    limit: int = 20,
    after: str | None = None,
) -> Any:
    """POST /crm/v3/objects/deals/search"""
    body: dict[str, Any] = {"limit": limit}
    if filters:
        body["filterGroups"] = [{"filters": filters}]
    if sorts:
        body["sorts"] = sorts
    if properties:
        body["properties"] = properties
    if after:
        body["after"] = after
    return await _request("POST", "/crm/v3/objects/deals/search", json_body=body)

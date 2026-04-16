"""HubSpot business-logic layer.

Sits between the API routes and the raw ``hubspot_client`` HTTP module.
Handles field mapping (DealDraft -> HubSpot properties) and response
normalization.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.integrations import hubspot_client
from app.integrations.hubspot_client import HubSpotAPIError
from app.schemas.hubspot_deal import (
    HubSpotDealCreateResponse,
    HubSpotDealDraft,
    HubSpotDealSearchResponse,
    HubSpotDealSearchResult,
    HubSpotDealUpdateResponse,
    HubSpotPipeline,
    HubSpotPipelineStage,
    HubSpotProperty,
    HubSpotPropertyOption,
    HubSpotUser,
)

logger = logging.getLogger(__name__)

# ── Field mapping: DealDraft field -> HubSpot internal property name ──────────
# Mirrors the FE ``DRAFT_TO_HUBSPOT_PROPERTY_CANDIDATE`` plus additional
# fields that map by convention (camelCase field -> lowercase HubSpot name).

_DRAFT_FIELD_TO_HUBSPOT: dict[str, str] = {
    "deal_name": "dealname",
    "pipeline": "pipeline",
    "market": "market",
    "status": "dealstage",
    "close_date": "closedate",
    "year_of_pipeline": "yearofpipeline",
    "owner": "hubspot_owner_id",
    "deal_sub_owner": "deal_sub_owner",
    "jp_section_lead": "jpsectionlead",
    "ea_section_lead": "ea_section_lead",
    "kr_section_lead": "kr_section_lead",
    "th_section_lead": "th_section_lead",
    "us_section_lead": "us_section_lead",
    "jp_delivery_manager": "jpdeliverymanager",
    "deal_type": "dealtypecustom",
    "contract_type": "contract_type",
    "service_category": "service_category",
    "service_ito_sub_category": "serviceitosub_category",
    "service_level": "service_level",
    "onsite_offshore_type": "onsiteoffshoretype",
    "onsite_unit_price": "onsiteunitprice",
    "offshore_unit_price": "offshoreunitprice",
    "onsite_delivery_team": "onsitedeliveryteam",
    "offshore_delivery_team": "offshoredeliveryteam",
    "payment_period_months": "payment_period",
    "presales": "presales",
    "priority": "priority_custom",
    "linked_company": "companies",
}


def _to_property_value(value: Any) -> str | None:
    """Serialize a draft field value to a HubSpot-compatible string."""
    if value is None or value == "":
        return None
    if isinstance(value, list):
        items = [str(v) for v in value if v]
        return ";".join(items) if items else None
    return str(value)


def draft_to_hubspot_properties(draft: HubSpotDealDraft) -> list[dict[str, str]]:
    """Convert a ``HubSpotDealDraft`` to the legacy v1 ``[{name, value}]`` format."""
    properties: list[dict[str, str]] = []
    draft_data = draft.model_dump(exclude_none=True, by_alias=False)

    for field_name, hs_name in _DRAFT_FIELD_TO_HUBSPOT.items():
        raw = draft_data.get(field_name)
        val = _to_property_value(raw)
        if val is not None:
            properties.append({"name": hs_name, "value": val})

    # Pass through extra fields not in our explicit map (FE may send
    # additional HubSpot property names directly as keys).
    known_fields = set(_DRAFT_FIELD_TO_HUBSPOT.keys()) | {"linked_company_label"}
    for key, raw in draft_data.items():
        if key not in known_fields:
            val = _to_property_value(raw)
            if val is not None:
                properties.append({"name": key, "value": val})

    return properties


# ── Metadata fetchers ─────────────────────────────────────────────────────────


def _normalize_pipeline(raw: dict[str, Any]) -> HubSpotPipeline:
    stages = [
        HubSpotPipelineStage(
            stageId=s.get("stageId", ""),
            label=s.get("label", ""),
            displayOrder=s.get("displayOrder", 0),
            archived=not s.get("active", True),
            metadata=s.get("metadata", {}),
        )
        for s in raw.get("stages", [])
    ]
    return HubSpotPipeline(
        pipelineId=raw.get("pipelineId", ""),
        label=raw.get("label", ""),
        displayOrder=raw.get("displayOrder", 0),
        archived=not raw.get("active", True),
        stages=stages,
    )


async def fetch_pipelines(object_type: str = "deals") -> list[HubSpotPipeline]:
    raw = await hubspot_client.get_pipelines(object_type)
    if isinstance(raw, list):
        return [_normalize_pipeline(p) for p in raw]
    if isinstance(raw, dict) and "results" in raw:
        return [_normalize_pipeline(p) for p in raw["results"]]
    return []


def _normalize_property(raw: dict[str, Any]) -> HubSpotProperty:
    options = [
        HubSpotPropertyOption(
            label=o.get("label", ""),
            value=o.get("value", ""),
            displayOrder=o.get("displayOrder", idx),
            hidden=o.get("hidden", False),
        )
        for idx, o in enumerate(raw.get("options", []))
    ]
    return HubSpotProperty(
        name=raw.get("name", ""),
        label=raw.get("label", ""),
        type=raw.get("type", ""),
        fieldType=raw.get("fieldType", "text"),
        options=options,
        formField=raw.get("formField", False),
        groupName=raw.get("groupName", ""),
        description=raw.get("description", ""),
        calculated=raw.get("calculated", False),
        modificationMetadata=raw.get("modificationMetadata", {}),
    )


async def fetch_deal_properties(
    object_type: str = "deals",
    *,
    form_field_only: bool = False,
) -> list[HubSpotProperty]:
    raw = await hubspot_client.get_properties(object_type)
    items = raw.get("results", []) if isinstance(raw, dict) else raw if isinstance(raw, list) else []
    props = [_normalize_property(p) for p in items]
    if form_field_only:
        props = [p for p in props if p.form_field]
    return props


def _normalize_user(raw: dict[str, Any]) -> HubSpotUser:
    return HubSpotUser(
        id=str(raw.get("id", "")),
        email=raw.get("email", ""),
        firstName=raw.get("firstName", ""),
        lastName=raw.get("lastName", ""),
    )


async def fetch_users() -> list[HubSpotUser]:
    raw = await hubspot_client.get_users()
    items = raw.get("results", []) if isinstance(raw, dict) else raw if isinstance(raw, list) else []
    return [_normalize_user(u) for u in items]


async def fetch_bootstrap() -> tuple[list[HubSpotPipeline], list[HubSpotProperty], list[HubSpotUser]]:
    """Pipelines + properties (``formField`` only) + users in parallel."""
    pipelines_coro = fetch_pipelines()
    props_coro = fetch_deal_properties(form_field_only=True)
    users_coro = fetch_users()
    pipelines, properties, users = await asyncio.gather(pipelines_coro, props_coro, users_coro)
    return pipelines, properties, users


# ── Deal CRUD ─────────────────────────────────────────────────────────────────


async def create_deal(draft: HubSpotDealDraft) -> HubSpotDealCreateResponse:
    """Map draft fields and create deal via HubSpot legacy v1 API."""
    properties = draft_to_hubspot_properties(draft)
    try:
        result = await hubspot_client.create_deal(properties)
    except HubSpotAPIError as exc:
        logger.error("HubSpot create_deal failed: %s (category=%s)", exc, exc.category)
        return HubSpotDealCreateResponse(
            success=False,
            hubspot_deal_id=None,
            message=f"HubSpot error: {exc}",
        )

    raw_id = result.get("dealId") or result.get("dealid") or result.get("id")
    deal_id = str(raw_id) if raw_id is not None else None
    is_success = bool(deal_id) and not result.get("isDeleted", False)

    return HubSpotDealCreateResponse(
        success=is_success,
        hubspot_deal_id=deal_id,
        message="Deal created in HubSpot" if is_success else "HubSpot returned an unexpected response",
    )


async def create_deal_from_list(properties: list[dict[str, str]]) -> HubSpotDealCreateResponse:
    """Create deal via HubSpot legacy v1 API from a raw list of properties."""
    try:
        result = await hubspot_client.create_deal(properties)
    except HubSpotAPIError as exc:
        logger.error("HubSpot create_deal_from_list failed: %s (category=%s)", exc, exc.category)
        return HubSpotDealCreateResponse(
            success=False,
            hubspot_deal_id=None,
            message=f"HubSpot error: {exc}",
        )

    raw_id = result.get("dealId") or result.get("dealid") or result.get("id")
    deal_id = str(raw_id) if raw_id is not None else None
    is_success = bool(deal_id) and not result.get("isDeleted", False)

    return HubSpotDealCreateResponse(
        success=is_success,
        hubspot_deal_id=deal_id,
        message="Deal created in HubSpot" if is_success else "HubSpot returned an unexpected response",
    )


async def update_deal(deal_id: str, draft: HubSpotDealDraft) -> HubSpotDealUpdateResponse:
    """Map draft fields and update an existing deal via HubSpot v3 API."""
    properties = draft_to_hubspot_properties(draft)
    try:
        result = await hubspot_client.update_deal(deal_id, properties)
    except HubSpotAPIError as exc:
        logger.error("HubSpot update_deal failed: %s (category=%s)", exc, exc.category)
        return HubSpotDealUpdateResponse(
            success=False,
            hubspot_deal_id=deal_id,
            message=f"HubSpot error: {exc}",
        )

    return HubSpotDealUpdateResponse(
        success=True,
        hubspot_deal_id=str(result.get("id", deal_id)),
        message="Deal updated in HubSpot",
    )


async def get_deal(deal_id: str) -> dict[str, Any] | None:
    try:
        return await hubspot_client.get_deal(deal_id)
    except HubSpotAPIError:
        return None


async def search_deals(
    *,
    filters: list[dict[str, Any]] | None = None,
    properties: list[str] | None = None,
    limit: int = 20,
    after: str | None = None,
) -> HubSpotDealSearchResponse:
    try:
        raw = await hubspot_client.search_deals(
            filters=filters,
            properties=properties,
            limit=limit,
            after=after,
        )
    except HubSpotAPIError as exc:
        logger.error("HubSpot search_deals failed: %s", exc)
        return HubSpotDealSearchResponse(total=0, results=[])

    results = [
        HubSpotDealSearchResult(
            id=r.get("id", ""),
            properties=r.get("properties", {}),
            createdAt=r.get("createdAt"),
            updatedAt=r.get("updatedAt"),
            archived=r.get("archived", False),
        )
        for r in raw.get("results", [])
    ]

    return HubSpotDealSearchResponse(
        total=raw.get("total", 0),
        results=results,
        paging=raw.get("paging"),
    )


# ── Reverse property mapping (for AI context) ────────────────────────────────
# HubSpot property names and option values are machine-readable IDs.
# When feeding deal data to the LLM, we need human-readable labels.
# See FE dev HoangVT's note: map name -> label, option value -> option label.


async def build_property_label_index() -> dict[str, HubSpotProperty]:
    """Fetch deal properties and return a lookup dict keyed by property ``name``."""
    props = await fetch_deal_properties()
    return {p.name: p for p in props}


def resolve_property_display(
    prop_name: str,
    prop_value: str,
    index: dict[str, HubSpotProperty],
) -> tuple[str, str]:
    """Resolve a property name/value pair to human-readable (label, display_value).

    Returns (property_label, resolved_value).  If the property or option is
    not found in the index, falls back to the raw name/value.
    """
    prop = index.get(prop_name)
    if not prop:
        return prop_name, prop_value

    display_label = prop.label or prop_name

    if not prop.options:
        return display_label, prop_value

    option_index = {o.value: o.label for o in prop.options}

    # Handle semicolon-separated multi-select values
    parts = prop_value.split(";") if ";" in prop_value else [prop_value]
    resolved_parts = [option_index.get(p.strip(), p.strip()) for p in parts]
    display_value = "; ".join(resolved_parts)

    return display_label, display_value


async def humanize_deal_properties(
    deal_properties: dict[str, str],
) -> dict[str, str]:
    """Convert a dict of ``{hs_property_name: raw_value}`` to ``{label: display_value}``.

    Useful for feeding deal context to the LLM in a readable format.
    """
    index = await build_property_label_index()
    result: dict[str, str] = {}
    for name, value in deal_properties.items():
        if not value:
            continue
        label, display = resolve_property_display(name, value, index)
        result[label] = display
    return result

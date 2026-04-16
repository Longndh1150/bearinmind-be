import logging

import httpx

logger = logging.getLogger(__name__)

async def get_available_staff(unit_id: str) -> list[dict]:
    """Task A - Fetch HRM staffing resource availability with fallback."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Stub HTTP call representing external HRM
            return [{"name": "Mock Staff", "role": "Developer"}]
    except (httpx.TimeoutException, httpx.RequestError) as e:
        logger.warning(f"HRM availability API error for unit {unit_id}: {e}")
        return []

async def get_unit_capacity(unit_id: str) -> dict:
    """Task A - Fetch HRM structured capacity overview with fallback."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Stub HTTP call representing external HRM
            return {"total_capacity": 100, "available": 20}
    except (httpx.TimeoutException, httpx.RequestError) as e:
        logger.warning(f"HRM capacity API error for unit {unit_id}: {e}")
        return {}

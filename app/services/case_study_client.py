import logging

import httpx

logger = logging.getLogger(__name__)

async def get_case_studies(unit_id: str) -> list[dict]:
    """Task B - Fetch normalized unit case studies from an upstream provider."""
    try:
        async with httpx.AsyncClient(timeout=10.0):
            # Stub HTTP call representation mapping upstream properties to normalized format
            return [{"title": "Mock Case Study", "tech_stack": ["Python", "AWS"]}]
    except (httpx.TimeoutException, httpx.RequestError) as e:
        logger.warning(f"HRM case study API error for unit {unit_id}: {e}")
        return []

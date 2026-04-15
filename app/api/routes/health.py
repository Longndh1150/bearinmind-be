from typing import Any

import redis.asyncio as redis
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_session

router = APIRouter(tags=["health"])


<<<<<<< HEAD
@router.get("/health/ready")
async def ready(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    await session.execute(text("SELECT 1"))
    checks: dict[str, str] = {"database": "connected"}

=======
@router.get("/health")
async def liveness() -> dict[str, str]:
    """Simple liveness probe — returns 200 immediately with no dependency checks."""
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    """Readiness probe — checks all downstream services but never crashes the app.

    Every check is wrapped in its own try/except so a missing service is
    reported as an error in the response body rather than an unhandled
    exception that would return a 5xx to the caller.
    """
    checks: dict[str, str] = {}

    # PostgreSQL
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "connected"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {exc!s}"

    # Redis
>>>>>>> origin/develop
    try:
        r = redis.from_url(settings.redis_url, decode_responses=True)
        await r.ping()
        await r.aclose()
        checks["redis"] = "connected"
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"error: {exc!s}"

<<<<<<< HEAD
=======
    # Chroma
>>>>>>> origin/develop
    try:
        import chromadb

        chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port).heartbeat()
        checks["chroma"] = "connected"
    except Exception as exc:  # noqa: BLE001
        checks["chroma"] = f"error: {exc!s}"

    return {"status": "ok", "checks": checks}

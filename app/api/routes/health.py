from typing import Any

import redis.asyncio as redis
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_session

router = APIRouter(tags=["health"])


@router.get("/health/ready")
async def ready(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    await session.execute(text("SELECT 1"))
    checks: dict[str, str] = {"database": "connected"}

    try:
        r = redis.from_url(settings.redis_url, decode_responses=True)
        await r.ping()
        await r.aclose()
        checks["redis"] = "connected"
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"error: {exc!s}"

    try:
        import chromadb

        chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port).heartbeat()
        checks["chroma"] = "connected"
    except Exception as exc:  # noqa: BLE001
        checks["chroma"] = f"error: {exc!s}"

    return {"status": "ok", "checks": checks}

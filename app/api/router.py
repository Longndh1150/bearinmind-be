from fastapi import APIRouter

from app.api.routes import auth, chat, health, hubspot, notifications, opportunities, units
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(chat.router)
api_router.include_router(opportunities.router)
api_router.include_router(units.router)
api_router.include_router(notifications.router)
api_router.include_router(hubspot.router)

if settings.app_env != "production":
    from app.api.routes import dev

    api_router.include_router(dev.router)

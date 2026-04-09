from fastapi import APIRouter

from app.api.routes import auth, chat, health, notifications, opportunities, units

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(chat.router)
api_router.include_router(opportunities.router)
api_router.include_router(units.router)
api_router.include_router(notifications.router)

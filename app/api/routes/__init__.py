from app.api.routes.auth import router as auth_router
from app.api.routes.chat import router as chat_router
from app.api.routes.health import router as health_router
from app.api.routes.hubspot_deals import router as hubspot_deals_router
from app.api.routes.notifications import router as notifications_router
from app.api.routes.opportunities import router as opportunities_router
from app.api.routes.units import router as units_router

__all__ = [
    "auth_router",
    "chat_router",
    "health_router",
    "hubspot_deals_router",
    "notifications_router",
    "opportunities_router",
    "units_router",
]

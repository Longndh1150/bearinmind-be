from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.schemas.auth import Token
from app.services.user_service import UserService


class AuthService:
    @staticmethod
    async def login(session: AsyncSession, *, email: str, password: str) -> Token | None:
        user = await UserService.authenticate(session, email=email, password=password)
        if not user:
            return None
        token = create_access_token(subject=user.id, email=user.email)
        return Token(access_token=token)


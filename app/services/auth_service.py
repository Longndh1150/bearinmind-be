from __future__ import annotations

import httpx
from fastapi import HTTPException
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

    @staticmethod
    async def login_microsoft(session: AsyncSession, access_token: str) -> Token:
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {access_token}"}
            response = await client.get("https://graph.microsoft.com/v1.0/me", headers=headers)
            
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid Microsoft access token")
            
        ms_data = response.json()
        
        # We assume `mail` or `identities` exist
        email = ms_data.get("mail") or ms_data.get("userPrincipalName", "")
        if not email:
            raise HTTPException(status_code=400, detail="Cannot find email in Microsoft account")
            
        ms_id = ms_data.get("id")
        full_name = ms_data.get("displayName", "")
        
        user = await UserService.get_or_create_microsoft_user(session, ms_id, email, full_name)
        token = create_access_token(subject=user.id, email=user.email)
        return Token(access_token=token)


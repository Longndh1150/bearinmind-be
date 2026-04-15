from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.auth import MicrosoftAuthLogin, Token
from app.schemas.user import UserCreate, UserLogin, UserPublic
from app.services.auth_service import AuthService
from app.services.user_service import UserService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserCreate,
    session: AsyncSession = Depends(get_session),
) -> UserPublic:
    existing = await UserService.get_by_email(session, str(payload.email).lower())
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = await UserService.create(session, payload)
    return UserPublic.model_validate(user, from_attributes=True)


@router.post("/login", response_model=Token)
async def login(
    payload: UserLogin,
    session: AsyncSession = Depends(get_session),
) -> Token:
    token = await AuthService.login(session, email=str(payload.email), password=payload.password)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return token

@router.post("/login/microsoft", response_model=Token)
async def login_microsoft(
    payload: MicrosoftAuthLogin,
    session: AsyncSession = Depends(get_session),
) -> Token:
    """Login or Register with Microsoft SSO"""
    token = await AuthService.login_microsoft(session, payload.access_token)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials from SSO")
    return token


from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_active_user, require_superuser
from app.db.session import get_session
from app.models.user import User
from app.schemas.common import Paginated
from app.schemas.user import UserPublic, UserUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserPublic, summary="Get current user")
async def get_current_user(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_active_user),
) -> UserPublic:
    return UserPublic.model_validate(current_user, from_attributes=True)


@router.get("", response_model=Paginated[UserPublic], summary="List users (superuser only)")
async def list_users(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    is_active: bool | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    _: object = Depends(require_superuser),
) -> Paginated[UserPublic]:
    items, total = await UserService.list_users(session, limit=limit, offset=offset, is_active=is_active)
    return Paginated(
        items=[UserPublic.model_validate(item, from_attributes=True) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/email/{email}", response_model=UserPublic, summary="Get user by email (superuser only)")
async def get_user_by_email(
    email: EmailStr,
    session: AsyncSession = Depends(get_session),
    _: object = Depends(require_superuser),
) -> UserPublic:
    user = await UserService.get_by_email(session, str(email).lower())
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserPublic.model_validate(user, from_attributes=True)


@router.get("/{user_id}", response_model=UserPublic, summary="Get user by ID (superuser only)")
async def get_user_by_id(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
    _: object = Depends(require_superuser),
) -> UserPublic:
    user = await UserService.get_by_id(session, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserPublic.model_validate(user, from_attributes=True)


@router.patch("/{user_id}", response_model=UserPublic, summary="Update user (superuser only)")
async def update_user(
    user_id: UUID,
    payload: UserUpdate,
    session: AsyncSession = Depends(get_session),
    _: object = Depends(require_superuser),
) -> UserPublic:
    user = await UserService.get_by_id(session, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if payload.email is not None:
        existing = await UserService.get_by_email(session, str(payload.email).lower())
        if existing and existing.id != user.id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = await UserService.update_user(session, user, payload)
    return UserPublic.model_validate(user, from_attributes=True)


@router.post("/{user_id}/activate", response_model=UserPublic, summary="Activate user (superuser only)")
async def activate_user(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
    _: object = Depends(require_superuser),
) -> UserPublic:
    user = await UserService.get_by_id(session, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user = await UserService.set_active(session, user, is_active=True)
    return UserPublic.model_validate(user, from_attributes=True)


@router.post("/{user_id}/deactivate", response_model=UserPublic, summary="Deactivate user (superuser only)")
async def deactivate_user(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
    _: object = Depends(require_superuser),
) -> UserPublic:
    user = await UserService.get_by_id(session, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user = await UserService.set_active(session, user, is_active=False)
    return UserPublic.model_validate(user, from_attributes=True)

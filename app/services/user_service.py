from __future__ import annotations

import uuid
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.models.user_microsoft import UserMicrosoft
from app.schemas.user import UserCreate, UserUpdate


class UserService:
    @staticmethod
    async def get_by_email(session: AsyncSession, email: str) -> User | None:
        res = await session.execute(select(User).where(User.email == email))
        return res.scalar_one_or_none()

    @staticmethod
    async def get_by_id(session: AsyncSession, user_id: UUID) -> User | None:
        return await session.get(User, user_id)

    @staticmethod
    async def list_users(
        session: AsyncSession,
        *,
        limit: int = 50,
        offset: int = 0,
        is_active: bool | None = None,
    ) -> tuple[list[User], int]:
        where_clause = []
        if is_active is not None:
            where_clause.append(User.is_active.is_(is_active))

        stmt = select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
        count_stmt = select(func.count()).select_from(User)
        if where_clause:
            stmt = stmt.where(*where_clause)
            count_stmt = count_stmt.where(*where_clause)

        rows = await session.execute(stmt)
        users = list(rows.scalars())
        total = int((await session.execute(count_stmt)).scalar_one())
        return users, total

    @staticmethod
    async def create(session: AsyncSession, data: UserCreate, *, is_superuser: bool = False) -> User:
        user = User(
            email=str(data.email).lower(),
            full_name=data.full_name,
            password_hash=hash_password(data.password),
            is_active=True,
            is_superuser=is_superuser,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

    @staticmethod
    async def update_user(session: AsyncSession, user: User, data: UserUpdate) -> User:
        updates = data.model_dump(exclude_unset=True)
        if "email" in updates:
            updates["email"] = str(updates["email"]).lower()
        for field, value in updates.items():
            setattr(user, field, value)
        await session.commit()
        await session.refresh(user)
        return user

    @staticmethod
    async def set_active(session: AsyncSession, user: User, *, is_active: bool) -> User:
        user.is_active = is_active
        await session.commit()
        await session.refresh(user)
        return user

    @staticmethod
    async def authenticate(session: AsyncSession, *, email: str, password: str) -> User | None:
        user = await UserService.get_by_email(session, str(email).lower())
        if not user:
            return None
        if not user.is_active:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    @staticmethod
    async def get_or_create_microsoft_user(session: AsyncSession, ms_id: str, email: str, full_name: str) -> User:
        email = email.lower()
        res = await session.execute(select(UserMicrosoft).where(UserMicrosoft.microsoft_id == ms_id))
        user_ms = res.scalar_one_or_none()

        if user_ms:
            res_user = await session.execute(select(User).where(User.id == user_ms.user_id))
            return res_user.scalar_one()

        res_existing_user = await session.execute(select(User).where(User.email == email))
        user = res_existing_user.scalar_one_or_none()

        if not user:
            # Create a new user with random password
            user = User(
                email=email,
                full_name=full_name,
                password_hash=hash_password(str(uuid.uuid4())),
                is_active=True,
                is_superuser=False,
            )
            session.add(user)
            await session.flush()

        user_ms = UserMicrosoft(
            user_id=user.id,
            microsoft_id=ms_id,
            email=email,
        )
        session.add(user_ms)
        await session.commit()
        await session.refresh(user)
        return user


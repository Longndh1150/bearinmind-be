from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=200)
    preferred_language: str = Field(default="vi", max_length=10)


class UserPublic(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str | None = None
    preferred_language: str
    is_active: bool
    is_superuser: bool
    created_at: datetime


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, max_length=200)
    preferred_language: str | None = Field(default=None, max_length=10)
    is_superuser: bool | None = None


from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
    email: str
    exp: int
    iat: int
    iss: str
    aud: str


class ErrorResponse(BaseModel):
    detail: str
    extra: dict[str, Any] | None = None


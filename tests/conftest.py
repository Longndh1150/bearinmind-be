"""Shared pytest fixtures."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.models.user import User


@pytest.fixture
def fake_user() -> User:
    return User(
        id=uuid4(),
        email="pytest@rikkei.com",
        full_name="Pytest User",
        password_hash="unused",
        is_active=True,
        is_superuser=False,
    )

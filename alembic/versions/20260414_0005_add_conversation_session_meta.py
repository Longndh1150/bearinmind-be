"""add session_meta JSONB column to conversations

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-14

"""

import sqlalchemy as sa
from collections.abc import Sequence

from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("session_meta", postgresql.JSONB(astext_type=None), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversations", "session_meta")

"""add ui_payload JSONB column to conversation_messages

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-14

Stores the full structured ChatResponse payload for assistant turns so that
GET /chat/conversations/{id} can replay the exact interactive UI without
re-running the LLM.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "conversation_messages",
        sa.Column("ui_payload", postgresql.JSONB(astext_type=None), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversation_messages", "ui_payload")

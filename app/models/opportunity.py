from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Opportunity(Base):
    """Sales opportunity — may be unofficial (from chat) or official (pushed to HubSpot)."""

    __tablename__ = "opportunities"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Lifecycle
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="draft", index=True)

    # Source tracking
    source: Mapped[str] = mapped_column(String(20), nullable=False, server_default="chat", index=True)
    is_official: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    pushed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hubspot_deal_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Structured extraction from LLM (JSONB for flexibility)
    extracted: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    client_info: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Owner (user who created / captured this opportunity)
    created_by_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Link back to the conversation that produced this opportunity (optional)
    conversation_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_opportunities_status_source", "status", "source"),
    )

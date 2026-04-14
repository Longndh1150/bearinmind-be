from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Unit(Base):
    """Internal division / delivery unit."""

    __tablename__ = "units"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")

    # Contact person for this unit
    contact_name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    contact_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Capability notes (free text, also embedded into Chroma)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Denormalised tech stack array for fast filtering (also stored in Chroma metadata)
    tech_stack: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    # Timestamps for re-embed trigger
    capabilities_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    experts: Mapped[list[UnitExpert]] = relationship(
        "UnitExpert", back_populates="unit", cascade="all, delete-orphan"
    )
    case_studies: Mapped[list[UnitCaseStudy]] = relationship(
        "UnitCaseStudy", back_populates="unit", cascade="all, delete-orphan"
    )


class UnitExpert(Base):
    """Named expert belonging to a unit, with focus areas."""

    __tablename__ = "unit_experts"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    unit_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    focus_areas: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    profile_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    unit: Mapped[Unit] = relationship("Unit", back_populates="experts")


class UnitCaseStudy(Base):
    """Case study linked to a unit; text is embedded into Chroma."""

    __tablename__ = "unit_case_studies"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    unit_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tech_stack: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    unit: Mapped[Unit] = relationship("Unit", back_populates="case_studies")

    __table_args__ = (Index("ix_unit_case_studies_unit_id", "unit_id"),)

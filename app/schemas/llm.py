from __future__ import annotations

from pydantic import BaseModel, Field


class LLMJsonParseError(BaseModel):
    """Use as a structured error when LLM output isn't valid JSON for a target schema."""

    message: str
    raw_output: str


class OpportunityExtract(BaseModel):
    """Example schema for parsing structured JSON from an LLM."""

    title: str | None = None
    client: str | None = None
    market: str | None = None
    tech_stack: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    notes: str | None = None


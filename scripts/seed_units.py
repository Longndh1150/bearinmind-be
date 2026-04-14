"""Seed sample unit data into ChromaDB.

Ported from BearInMind/app/seed_data.py; uses bearinmind-be settings and
the shared vector_search tool so the collection name stays consistent.

Usage:
    python -m scripts.seed_units
    # or with uv:
    uv run python -m scripts.seed_units
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on path when run directly
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai.tools.vector_search import index_unit


def seed() -> None:
    print("Seeding unit capabilities into ChromaDB…")

    index_unit(
        unit_id="unit-001",
        unit_name="Rikkei D365 Division",
        tech_stack=["D365", "Power Platform", "C#", "Azure"],
        case_studies=(
            "Deployed D365 CRM for a retail chain in Tokyo, Japan. "
            "Implemented D365 Business Central for a manufacturing client in APAC."
        ),
        contact_name="ThangLB",
    )

    index_unit(
        unit_id="unit-002",
        unit_name="Rikkei AI & Data",
        tech_stack=["Python", "LLM", "OpenAI", "ChromaDB", "LangChain"],
        case_studies=(
            "Built an AI-powered matching system for internal operations. "
            "Developed a data pipeline and analytics dashboard for a fintech client."
        ),
        contact_name="MinhLN",
    )

    index_unit(
        unit_id="unit-003",
        unit_name="Rikkei Java Division",
        tech_stack=["Java", "Spring Boot", "Microservices", "AWS"],
        case_studies=(
            "Delivered a large-scale e-commerce backend for a Japanese retailer. "
            "Migrated a legacy monolith to microservices for a logistics company."
        ),
        contact_name="HungNT",
    )

    print("Done — 3 units indexed.")


if __name__ == "__main__":
    seed()

"""Seed sample unit data into ChromaDB.

Uses STABLE UUIDs so this script is idempotent — running it multiple times
will upsert (update) the same records rather than creating duplicates.

These UUIDs should also be used as the primary key when inserting the same
units into PostgreSQL (via a future DB seed or Alembic data migration).

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

# ── Stable seed UUIDs ─────────────────────────────────────────────────────────
# These are fixed so the script is idempotent and can be referenced by other
# scripts (e.g. DB seed) to keep Chroma IDs and Postgres PKs in sync.
UNIT_D365_ID = "a1b2c3d4-0001-0001-0001-000000000001"
UNIT_AI_DATA_ID = "a1b2c3d4-0002-0002-0002-000000000002"
UNIT_JAVA_ID = "a1b2c3d4-0003-0003-0003-000000000003"

SEED_UNITS = [
    {
        "unit_id": UNIT_D365_ID,
        "unit_name": "Rikkei D365 Division",
        "tech_stack": ["D365", "Power Platform", "C#", "Azure"],
        "case_studies": (
            "Deployed D365 CRM for a retail chain in Tokyo, Japan. "
            "Implemented D365 Business Central for a manufacturing client in APAC."
        ),
        "case_study_titles": ["D365 CRM — Tokyo Retail", "D365 Business Central — APAC Mfg"],
        "contact_name": "ThangLB",
    },
    {
        "unit_id": UNIT_AI_DATA_ID,
        "unit_name": "Rikkei AI & Data",
        "tech_stack": ["Python", "LLM", "OpenAI", "ChromaDB", "LangChain"],
        "case_studies": (
            "Built an AI-powered matching system for internal operations. "
            "Developed a data pipeline and analytics dashboard for a fintech client."
        ),
        "case_study_titles": ["AI Matching System", "Fintech Analytics Dashboard"],
        "contact_name": "HieuNN",
    },
    {
        "unit_id": UNIT_JAVA_ID,
        "unit_name": "Rikkei Java Division",
        "tech_stack": ["Java", "Spring Boot", "Microservices", "AWS"],
        "case_studies": (
            "Delivered a large-scale e-commerce backend for a Japanese retailer. "
            "Migrated a legacy monolith to microservices for a logistics company."
        ),
        "case_study_titles": ["E-commerce Backend — Japan Retailer", "Microservices Migration — Logistics"],
        "contact_name": "HungDT",
    },
]


def seed() -> None:
    print("Seeding unit capabilities into ChromaDB…")
    for unit in SEED_UNITS:
        index_unit(**unit)
        print(f"  ✓ {unit['unit_name']}  (id={unit['unit_id']})")
    print(f"Done — {len(SEED_UNITS)} units indexed (upserted).")


if __name__ == "__main__":
    seed()

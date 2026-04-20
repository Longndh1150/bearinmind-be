"""Seed Unit capability data (D.Lead source) into PostgreSQL + vector index.

This script seeds the curated Unit dataset owned by D.Lead (division lead):
- Unit profile/contact
- Tech stack / notes
- Experts
- Case studies

Important:
- This is only the D.Lead-maintained source of truth for unit capabilities.
- Detailed HRM staffing availability is a separate data source and should be
  seeded/mocked independently, then merged in agent workflows.

Usage:
    python -m scripts.seed.units
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import chromadb
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.unit import Unit, UnitCaseStudy, UnitExpert
from app.services.unit_vector_indexer import reindex_unit

SEED_UNITS: list[dict[str, Any]] = [
    {
        "code": "D1",
        "name": "D1",
        "contact_name": "Lead D1",
        "contact_email": "d1_lead@rikkeisoft.com",
        "contact_title": "Division Lead",
        "tech_stack": ["Java", "Spring Boot", "Microservices", "PostgreSQL"],
        "notes": "Strong in enterprise modernization and backend platforms.",
        "experts": [
            {"name": "DevA D1", "focus_areas": ["Spring Boot", "DDD"]},
        ],
        "case_studies": [
            {
                "title": "Retail Platform",
                "domain": "Retail",
                "tech_stack": ["Java", "Spring Boot", "Kafka"],
                "description": "Migrated monolith to microservices.",
                "url": "https://example.internal/case/d1-retail",
            },
        ],
    },
    {
        "code": "D2",
        "name": "D2",
        "contact_name": "Lead D2",
        "contact_email": "d2_lead@rikkeisoft.com",
        "contact_title": "Division Lead",
        "tech_stack": ["Go", "Kubernetes", "AWS", "Terraform"],
        "notes": "Cloud-native platform engineering.",
        "experts": [
            {"name": "DevB D2", "focus_areas": ["Go", "Kubernetes"]},
        ],
        "case_studies": [
            {
                "title": "Banking CI/CD",
                "domain": "Banking",
                "tech_stack": ["Kubernetes", "Terraform"],
                "description": "Standardized deployment platform.",
                "url": "https://example.internal/case/d2-banking-cicd",
            },
        ],
    },
    {
        "code": "D5",
        "name": "D5",
        "contact_name": "Lead D5",
        "contact_email": "d5_lead@rikkeisoft.com",
        "contact_title": "Division Lead",
        "tech_stack": ["Python", "Airflow", "Spark", "Snowflake"],
        "notes": "Data pipelines and integration.",
        "experts": [
            {"name": "DevC D5", "focus_areas": ["Airflow", "Spark"]},
        ],
        "case_studies": [
            {
                "title": "Data Lakehouse",
                "domain": "Insurance",
                "tech_stack": ["Spark", "Snowflake"],
                "description": "Unified data lakehouse.",
                "url": "https://example.internal/case/d5-data-lakehouse",
            },
        ],
    },
    {
        "code": "D6",
        "name": "D6",
        "contact_name": "Lead D6",
        "contact_email": "d6_lead@rikkeisoft.com",
        "contact_title": "Division Lead",
        "tech_stack": ["React", "TypeScript", "Node.js", "GraphQL"],
        "notes": "Fullstack web platforms.",
        "experts": [
            {"name": "DevD D6", "focus_areas": ["React", "Node.js"]},
        ],
        "case_studies": [
            {
                "title": "Billing Portal",
                "domain": "SaaS",
                "tech_stack": ["React", "Node.js"],
                "description": "Billing management portal.",
                "url": "https://example.internal/case/d6-billing",
            },
        ],
    },
    {
        "code": "D8",
        "name": "D8",
        "contact_name": "Lead D8",
        "contact_email": "d8_lead@rikkeisoft.com",
        "contact_title": "Division Lead",
        "tech_stack": ["Flutter", "Kotlin", "Swift", "Firebase"],
        "notes": "Mobile apps.",
        "experts": [
            {"name": "DevE D8", "focus_areas": ["Flutter", "Firebase"]},
        ],
        "case_studies": [
            {
                "title": "Super App",
                "domain": "Retail",
                "tech_stack": ["Flutter", "Firebase"],
                "description": "Omnichannel mobile app.",
                "url": "https://example.internal/case/d8-super-app",
            },
        ],
    },
    {
        "code": "G0",
        "name": "G0",
        "contact_name": "Lead G0",
        "contact_email": "g0_lead@rikkeisoft.com",
        "contact_title": "Division Lead",
        "tech_stack": ["Playwright", "Python", "TestRail"],
        "notes": "QA and test automation.",
        "experts": [
            {"name": "DevF G0", "focus_areas": ["Playwright", "QA"]},
        ],
        "case_studies": [
            {
                "title": "Regression Factory",
                "domain": "Finance",
                "tech_stack": ["Playwright", "Jenkins"],
                "description": "Automated regression testing.",
                "url": "https://example.internal/case/g0-regression",
            },
        ],
    },
    {
        "code": "G8",
        "name": "G8",
        "contact_name": "Lead G8",
        "contact_email": "g8_lead@rikkeisoft.com",
        "contact_title": "Division Lead",
        "tech_stack": ["C/C++", "Embedded Linux", "RTOS", "IoT"],
        "notes": "Embedded systems and IoT.",
        "experts": [
            {"name": "DevG G8", "focus_areas": ["Embedded Linux", "RTOS"]},
        ],
        "case_studies": [
            {
                "title": "Sensor Gateway",
                "domain": "Manufacturing",
                "tech_stack": ["C++", "IoT"],
                "description": "IoT Gateway firmware.",
                "url": "https://example.internal/case/g8-gateway",
            },
        ],
    },
    {
        "code": "G10",
        "name": "G10",
        "contact_name": "Lead G10",
        "contact_email": "g10_lead@rikkeisoft.com",
        "contact_title": "Division Lead",
        "tech_stack": [".NET", "Azure", "SQL Server"],
        "notes": "Enterprise integration.",
        "experts": [
            {"name": "DevH G10", "focus_areas": [".NET", "Azure"]},
        ],
        "case_studies": [
            {
                "title": "Workflow Digitization",
                "domain": "Enterprise",
                "tech_stack": [".NET", "Azure"],
                "description": "Internal workflow digitization.",
                "url": "https://example.internal/case/g10-workflow",
            },
        ],
    },
    {
        "code": "DN1",
        "name": "DN1",
        "contact_name": "Lead DN1",
        "contact_email": "dn1_lead@rikkeisoft.com",
        "contact_title": "Division Lead",
        "tech_stack": ["Java", "Oracle", "Legacy Modernization"],
        "notes": "Legacy modernization and enterprise support.",
        "experts": [
            {"name": "DevI DN1", "focus_areas": ["Java", "Legacy"]},
        ],
        "case_studies": [
            {
                "title": "Legacy Renewal",
                "domain": "Retail",
                "tech_stack": ["Java", "Oracle"],
                "description": "Modernized legacy systems.",
                "url": "https://example.internal/case/dn1-legacy",
            },
        ],
    },
    {
        "code": "DN3",
        "name": "DN3",
        "contact_name": "Lead DN3",
        "contact_email": "dn3_lead@rikkeisoft.com",
        "contact_title": "Division Lead",
        "tech_stack": ["Python", "LLM", "LangChain", "RAG"],
        "notes": "AI Platform & Applied GenAI.",
        "experts": [
            {"name": "DevJ DN3", "focus_areas": ["RAG", "LangChain"]},
        ],
        "case_studies": [
            {
                "title": "Opportunity Matching Copilot",
                "domain": "Sales",
                "tech_stack": ["Python", "RAG"],
                "description": "AI assistant for opportunity matching.",
                "url": "https://example.internal/case/dn3-ai-copilot",
            },
        ],
    },
    {
        "code": "HU1",
        "name": "HU1",
        "contact_name": "Lead HU1",
        "contact_email": "hu1_lead@rikkeisoft.com",
        "contact_title": "Division Lead",
        "tech_stack": ["SAP", "Salesforce", "Integration"],
        "notes": "ERP & CRM integration.",
        "experts": [
            {"name": "DevK HU1", "focus_areas": ["SAP", "Salesforce"]},
        ],
        "case_studies": [
            {
                "title": "SAP CRM Integration",
                "domain": "Enterprise",
                "tech_stack": ["SAP", "API"],
                "description": "Enterprise CRM and ERP integration.",
                "url": "https://example.internal/case/hu1-sap-crm",
            },
        ],
    },
    {
        "code": "HM1",
        "name": "HM1",
        "contact_name": "Lead HM1",
        "contact_email": "hm1_lead@rikkeisoft.com",
        "contact_title": "Division Lead",
        "tech_stack": ["Vue.js", "PHP", "Laravel"],
        "notes": "Web and CMS systems.",
        "experts": [
            {"name": "DevL HM1", "focus_areas": ["Vue.js", "CMS"]},
        ],
        "case_studies": [
            {
                "title": "CMS Platform",
                "domain": "Media",
                "tech_stack": ["Vue.js", "PHP"],
                "description": "Built scalable CMS platform.",
                "url": "https://example.internal/case/hm1-cms",
            },
        ],
    },
]


def _ensure_contact_name(payload: dict[str, Any]) -> str:
    """Return a non-empty contact name for DB not-null safety."""
    raw = payload.get("contact_name")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()

    code = str(payload.get("code") or "UNIT").strip() or "UNIT"
    return f"{code} Lead"


async def _upsert_unit(session: AsyncSession, payload: dict[str, Any]) -> Unit:
    contact_name = _ensure_contact_name(payload)

    stmt = (
        select(Unit)
        .where(Unit.code == payload["code"])
        .options(selectinload(Unit.experts), selectinload(Unit.case_studies))
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()

    if existing is None:
        # Populate required not-null fields up front; first flush would otherwise fail.
        unit = Unit(
            code=payload["code"],
            name=payload["name"],
            contact_name=contact_name,
        )
        session.add(unit)
    else:
        unit = existing

    unit.name = payload["name"]
    unit.status = "active"
    unit.contact_name = contact_name
    unit.contact_email = payload.get("contact_email")
    unit.contact_title = payload.get("contact_title")
    unit.contact_phone = payload.get("contact_phone")
    unit.tech_stack = payload.get("tech_stack", [])
    unit.notes = payload.get("notes")
    unit.capabilities_updated_at = datetime.now(UTC)

    unit.experts.clear()
    for exp in payload.get("experts", []):
        unit.experts.append(
            UnitExpert(
                name=exp["name"],
                focus_areas=exp.get("focus_areas", []),
                profile_url=exp.get("profile_url"),
            )
        )

    unit.case_studies.clear()
    for cs in payload.get("case_studies", []):
        unit.case_studies.append(
            UnitCaseStudy(
                title=cs["title"],
                domain=cs.get("domain"),
                tech_stack=cs.get("tech_stack", []),
                description=cs.get("description"),
                url=cs.get("url"),
            )
        )

    await session.flush()
    return unit


async def seed_units() -> None:
    print("Seeding unit data into PostgreSQL (D.Lead source) ...")
    async with AsyncSessionLocal() as session:
        unit_ids: list[str] = []

        for payload in SEED_UNITS:
            unit = await _upsert_unit(session, payload)
            unit_ids.append(str(unit.id))
            print(
                f"  [OK] {unit.code} - {unit.name} "
                f"(experts={len(unit.experts)}, case_studies={len(unit.case_studies)})"
            )

        await session.commit()

        print("Re-indexing units into vector store ...")
        from app.ai.tools.vector_search import get_chroma_client
        try:
            client = get_chroma_client()
            client.delete_collection(name="unit_capabilities")
            print("Đã xóa collection cũ thành công.")
        except Exception as e:
            print(f"Không tìm thấy collection hoặc lỗi: {e}")
        for uid in unit_ids:
            await reindex_unit(uid, session=session)
        print(f"Done - {len(unit_ids)} unit(s) seeded and indexed.")


def main() -> None:
    import asyncio

    asyncio.run(seed_units())


if __name__ == "__main__":
    main()

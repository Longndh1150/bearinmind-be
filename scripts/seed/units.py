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
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionLocal
from app.models.unit import Unit, UnitCaseStudy, UnitExpert
from app.services.unit_vector_indexer import reindex_unit

import chromadb
from app.core.config import settings
from pathlib import Path

SEED_UNITS: list[dict[str, Any]] = [
    {
        "code": "DN1",
        "name": "DN1 Enterprise Apps",
        "contact_name": "QuangPM",
        "contact_email": "quangpm@rikkeisoft.com",
        "contact_title": "Division Lead",
        "tech_stack": ["Java", "Spring Boot", "Microservices", "AWS", "PostgreSQL", "Kafka"],
        "notes": "Strong in enterprise modernization and high-throughput backend platforms.",
        "experts": [
            {"name": "LamNT", "focus_areas": ["Spring Boot", "Domain-driven design"]},
            {"name": "NghiaPH", "focus_areas": ["Kafka", "Event streaming"]},
            {"name": "KhanhLM", "focus_areas": ["AWS EKS", "Infrastructure as Code"]},
            {"name": "HieuTV", "focus_areas": ["Performance tuning", "Caching"]},
            {"name": "PhuocND", "focus_areas": ["Payments", "Settlement workflows"]},
            {"name": "TrangVT", "focus_areas": ["Quality engineering", "Test automation"]},
        ],
        "case_studies": [
            {
                "title": "Retail Loyalty Platform Revamp",
                "domain": "Retail",
                "tech_stack": ["Java", "Spring Boot", "Kafka", "Redis"],
                "description": "Migrated monolith to microservices for JP retailer loyalty system.",
                "url": "https://example.internal/case/dn1-retail-loyalty",
            },
            {
                "title": "Digital Wallet Core APIs",
                "domain": "Fintech",
                "tech_stack": ["Java", "PostgreSQL", "AWS"],
                "description": "Built secure transaction APIs and reconciliation jobs for wallet product.",
                "url": "https://example.internal/case/dn1-wallet",
            },
            {
                "title": "Logistics SLA Alerting",
                "domain": "Logistics",
                "tech_stack": ["Kafka", "Elasticsearch", "Grafana"],
                "description": "Implemented streaming SLA breach detection pipeline and ops dashboard.",
                "url": "https://example.internal/case/dn1-logistics-sla",
            },
        ],
    },
    {
        "code": "DN2",
        "name": "DN2 Cloud Platforms",
        "contact_name": "MinhTQ",
        "contact_email": "minhtq@rikkeisoft.com",
        "contact_title": "Division Lead",
        "tech_stack": ["Go", "Kubernetes", "AWS", "Terraform", "Prometheus", "ArgoCD"],
        "notes": "Cloud-native platform engineering with strong DevSecOps discipline.",
        "experts": [
            {"name": "HuyDT", "focus_areas": ["Go", "gRPC"]},
            {"name": "LongNV", "focus_areas": ["Kubernetes", "Cluster operations"]},
            {"name": "DatTT", "focus_areas": ["Terraform", "IaC standards"]},
            {"name": "PhucHT", "focus_areas": ["ArgoCD", "GitOps"]},
            {"name": "DuyPA", "focus_areas": ["SRE", "Observability"]},
            {"name": "YenLN", "focus_areas": ["Cloud security", "Compliance"]},
            {"name": "BaoNQ", "focus_areas": ["Cost optimization", "FinOps"]},
        ],
        "case_studies": [
            {
                "title": "Banking CI/CD Golden Path",
                "domain": "Banking",
                "tech_stack": ["Kubernetes", "ArgoCD", "Terraform"],
                "description": "Designed standardized deployment platform for 40+ services.",
                "url": "https://example.internal/case/dn2-golden-path",
            },
            {
                "title": "EKS Multi-tenant Runtime",
                "domain": "SaaS",
                "tech_stack": ["Go", "Kubernetes", "AWS"],
                "description": "Built multi-tenant control plane components with policy guardrails.",
                "url": "https://example.internal/case/dn2-multitenant",
            },
        ],
    },
    {
        "code": "DN3",
        "name": "DN3 Data & Integration",
        "contact_name": "LinhNH",
        "contact_email": "linhnh@rikkeisoft.com",
        "contact_title": "Division Lead",
        "tech_stack": ["Python", "Airflow", "Spark", "dbt", "Snowflake", "Kafka"],
        "notes": "Specialized in data pipelines and cross-system integration projects.",
        "experts": [
            {"name": "HaPT", "focus_areas": ["Airflow", "Workflow orchestration"]},
            {"name": "TuanBV", "focus_areas": ["Spark", "Distributed processing"]},
            {"name": "MyDL", "focus_areas": ["dbt", "Data modeling"]},
            {"name": "ThaoNT", "focus_areas": ["Snowflake", "Warehouse optimization"]},
            {"name": "KietLQ", "focus_areas": ["Kafka Connect", "CDC"]},
            {"name": "SonVD", "focus_areas": ["Data governance", "Metadata"]},
        ],
        "case_studies": [
            {
                "title": "Insurance Data Lakehouse",
                "domain": "Insurance",
                "tech_stack": ["Spark", "Airflow", "Snowflake"],
                "description": "Unified policy and claim datasets with quality and lineage controls.",
                "url": "https://example.internal/case/dn3-insurance-lakehouse",
            },
            {
                "title": "Omnichannel CDP Feed",
                "domain": "Retail",
                "tech_stack": ["Python", "Kafka", "dbt"],
                "description": "Real-time + batch ingestion for customer data platform activation.",
                "url": "https://example.internal/case/dn3-cdp",
            },
            {
                "title": "ERP to CRM Data Sync",
                "domain": "Enterprise",
                "tech_stack": ["Airflow", "Python", "PostgreSQL"],
                "description": "Scheduled + event-driven synchronization across ERP and CRM systems.",
                "url": "https://example.internal/case/dn3-erp-crm",
            },
        ],
    },
    {
        "code": "HU",
        "name": "HU Embedded & IoT",
        "contact_name": "HungPB",
        "contact_email": "hungpb@rikkeisoft.com",
        "contact_title": "Division Lead",
        "tech_stack": ["C/C++", "Embedded Linux", "RTOS", "MQTT", "Edge AI"],
        "notes": "Strong in edge device firmware, telemetry ingestion, and gateway software.",
        "experts": [
            {"name": "VietNQ", "focus_areas": ["Embedded Linux", "Kernel tuning"]},
            {"name": "KhoaLT", "focus_areas": ["RTOS", "Firmware architecture"]},
            {"name": "NhanTT", "focus_areas": ["MQTT", "Device protocols"]},
            {"name": "AnNP", "focus_areas": ["Computer vision", "Edge inference"]},
            {"name": "PhatTD", "focus_areas": ["Device security", "OTA updates"]},
        ],
        "case_studies": [
            {
                "title": "Factory Sensor Gateway",
                "domain": "Manufacturing",
                "tech_stack": ["C++", "MQTT", "Embedded Linux"],
                "description": "Built gateway firmware for predictive maintenance sensor fleet.",
                "url": "https://example.internal/case/hu-factory-gateway",
            },
            {
                "title": "Smart Camera Edge Pipeline",
                "domain": "Smart City",
                "tech_stack": ["Edge AI", "C++", "RTOS"],
                "description": "Optimized edge inference runtime for traffic incident detection.",
                "url": "https://example.internal/case/hu-smart-camera",
            },
        ],
    },
    {
        "code": "HN1",
        "name": "HN1 Web Products",
        "contact_name": "KienNM",
        "contact_email": "kiennm@rikkeisoft.com",
        "contact_title": "Division Lead",
        "tech_stack": ["TypeScript", "React", "Node.js", "PostgreSQL", "GraphQL"],
        "notes": "Product-oriented fullstack teams for fast-moving web platforms.",
        "experts": [
            {"name": "NgocHT", "focus_areas": ["React", "Design systems"]},
            {"name": "ToanVV", "focus_areas": ["Node.js", "API design"]},
            {"name": "LanPT", "focus_areas": ["GraphQL", "Schema federation"]},
            {"name": "BinhVH", "focus_areas": ["Auth", "Identity"]},
            {"name": "TramNH", "focus_areas": ["UX", "Product discovery"]},
            {"name": "QuocPN", "focus_areas": ["Performance", "Frontend observability"]},
        ],
        "case_studies": [
            {
                "title": "Subscription Billing Portal",
                "domain": "SaaS",
                "tech_stack": ["React", "Node.js", "PostgreSQL"],
                "description": "Delivered self-service billing and plan management portal.",
                "url": "https://example.internal/case/hn1-billing-portal",
            },
            {
                "title": "GraphQL BFF for Retail App",
                "domain": "Retail",
                "tech_stack": ["GraphQL", "TypeScript", "Redis"],
                "description": "Built backend-for-frontend to reduce mobile app integration complexity.",
                "url": "https://example.internal/case/hn1-graphql-bff",
            },
            {
                "title": "Customer Support Workspace",
                "domain": "Customer Service",
                "tech_stack": ["React", "Node.js", "WebSocket"],
                "description": "Implemented agent workspace with realtime ticket collaboration.",
                "url": "https://example.internal/case/hn1-support-workspace",
            },
        ],
    },
    {
        "code": "HN2",
        "name": "HN2 Mobile & Commerce",
        "contact_name": "AnhLQ",
        "contact_email": "anhlq@rikkeisoft.com",
        "contact_title": "Division Lead",
        "tech_stack": ["Flutter", "Kotlin", "Swift", "Firebase", "Node.js"],
        "notes": "Cross-platform and native mobile teams for commerce and loyalty products.",
        "experts": [
            {"name": "PhuongDT", "focus_areas": ["Flutter", "Architecture"]},
            {"name": "HaiDN", "focus_areas": ["Kotlin", "Android performance"]},
            {"name": "TrangHL", "focus_areas": ["Swift", "iOS architecture"]},
            {"name": "DucNT", "focus_areas": ["Mobile CI/CD", "Release automation"]},
            {"name": "HuongPT", "focus_areas": ["Payment SDK", "Wallet flows"]},
            {"name": "VuPA", "focus_areas": ["Firebase", "Push notifications"]},
        ],
        "case_studies": [
            {
                "title": "Retail Super App",
                "domain": "Retail",
                "tech_stack": ["Flutter", "Firebase", "Node.js"],
                "description": "Built omnichannel super app with loyalty and ordering modules.",
                "url": "https://example.internal/case/hn2-super-app",
            },
            {
                "title": "Cross-border Shopping App",
                "domain": "E-commerce",
                "tech_stack": ["Swift", "Kotlin", "GraphQL"],
                "description": "Native app suite with localized checkout and shipment tracking.",
                "url": "https://example.internal/case/hn2-cross-border",
            },
        ],
    },
    {
        "code": "HN3",
        "name": "HN3 QA & Delivery Excellence",
        "contact_name": "ThangNV",
        "contact_email": "thangnv@rikkeisoft.com",
        "contact_title": "Division Lead",
        "tech_stack": ["Playwright", "Cypress", "Python", "JUnit", "K6", "TestRail"],
        "notes": "Quality-first squad with automation, performance, and release governance expertise.",
        "experts": [
            {"name": "LuanTM", "focus_areas": ["Test architecture", "Quality strategy"]},
            {"name": "GiangPT", "focus_areas": ["Playwright", "E2E automation"]},
            {"name": "DuongMN", "focus_areas": ["API testing", "Contract testing"]},
            {"name": "SonHP", "focus_areas": ["Performance testing", "K6"]},
            {"name": "NgaTT", "focus_areas": ["Security testing", "SAST/DAST"]},
            {"name": "LocNN", "focus_areas": ["Release governance", "Defect analytics"]},
            {"name": "KhanhPT", "focus_areas": ["Mobile testing", "Device farms"]},
        ],
        "case_studies": [
            {
                "title": "Banking Regression Factory",
                "domain": "Banking",
                "tech_stack": ["Playwright", "JUnit", "Jenkins"],
                "description": "Reduced release regression cycle from 5 days to under 1 day.",
                "url": "https://example.internal/case/hn3-regression-factory",
            },
            {
                "title": "Perf Baseline Program",
                "domain": "E-commerce",
                "tech_stack": ["K6", "Grafana", "Python"],
                "description": "Established performance SLO baseline and pre-release gates.",
                "url": "https://example.internal/case/hn3-perf-baseline",
            },
            {
                "title": "API Contract Compliance",
                "domain": "SaaS",
                "tech_stack": ["Python", "OpenAPI", "Schemathesis"],
                "description": "Automated API contract checks integrated into CI pipelines.",
                "url": "https://example.internal/case/hn3-contract-compliance",
            },
        ],
    },
    {
        "code": "HCM",
        "name": "HCM Digital Solutions",
        "contact_name": "ThanhPT",
        "contact_email": "thanhpt@rikkeisoft.com",
        "contact_title": "Division Lead",
        "tech_stack": [".NET", "Azure", "React", "SQL Server", "Power Platform"],
        "notes": "Balanced frontend/backend teams for enterprise digital transformation.",
        "experts": [
            {"name": "HaoNT", "focus_areas": [".NET", "Clean architecture"]},
            {"name": "VyTT", "focus_areas": ["Azure", "Cloud integration"]},
            {"name": "KhangDQ", "focus_areas": ["Power Platform", "Process automation"]},
            {"name": "TienLT", "focus_areas": ["React", "Enterprise UX"]},
            {"name": "TrucPH", "focus_areas": ["SQL Server", "Data migration"]},
            {"name": "NhatTK", "focus_areas": ["Identity", "Access control"]},
        ],
        "case_studies": [
            {
                "title": "Manufacturing Workflow Digitization",
                "domain": "Manufacturing",
                "tech_stack": [".NET", "Power Platform", "Azure"],
                "description": "Digitized approval workflows and integrated with legacy ERP.",
                "url": "https://example.internal/case/hcm-workflow",
            },
            {
                "title": "Field Service Scheduling",
                "domain": "Field Service",
                "tech_stack": [".NET", "React", "Azure"],
                "description": "Built scheduling console and technician mobile companion APIs.",
                "url": "https://example.internal/case/hcm-field-service",
            },
        ],
    },
    {
        "code": "JP",
        "name": "JP Delivery & Localization",
        "contact_name": "SatoKen",
        "contact_email": "satoken@rikkeisoft.com",
        "contact_title": "Division Lead",
        "tech_stack": ["Java", "Python", "Bilingual BA", "Legacy modernization", "SAP integration"],
        "notes": "Japanese market delivery unit with strong bilingual bridging and onsite-offshore model.",
        "experts": [
            {"name": "YamadaAkira", "focus_areas": ["JP business analysis", "Stakeholder management"]},
            {"name": "MaiNT", "focus_areas": ["Localization QA", "UAT support"]},
            {"name": "KobayashiRyo", "focus_areas": ["Modernization planning", "Risk control"]},
            {"name": "TungND", "focus_areas": ["Java backend", "Integration"]},
            {"name": "HanhLT", "focus_areas": ["Python automation", "Data scripts"]},
            {"name": "PhuongNB", "focus_areas": ["SAP integration", "Enterprise process"]},
        ],
        "case_studies": [
            {
                "title": "JP Retail Legacy Renewal",
                "domain": "Retail",
                "tech_stack": ["Java", "Oracle", "Batch modernization"],
                "description": "Phased modernization roadmap with bilingual governance model.",
                "url": "https://example.internal/case/jp-legacy-renewal",
            },
            {
                "title": "Insurance Claims Workflow JP",
                "domain": "Insurance",
                "tech_stack": ["Python", "Java", "Workflow automation"],
                "description": "Localized claims process and improved cross-team lead time.",
                "url": "https://example.internal/case/jp-claims",
            },
            {
                "title": "SAP-CRM Data Mediation",
                "domain": "Enterprise",
                "tech_stack": ["SAP", "ETL", "API integration"],
                "description": "Built data mediation layer between SAP and cloud CRM systems.",
                "url": "https://example.internal/case/jp-sap-crm",
            },
        ],
    },
    {
        "code": "AI",
        "name": "AI Platform & Applied GenAI",
        "contact_name": "HieuNN",
        "contact_email": "hieunn@rikkeisoft.com",
        "contact_title": "Division Lead",
        "tech_stack": ["Python", "LLM", "LangChain", "RAG", "Vector DB", "MLOps"],
        "notes": "Applied AI team focusing on LLM products, retrieval, and automation workflows.",
        "experts": [
            {"name": "HoangVT", "focus_areas": ["Agentic systems", "LangGraph"]},
            {"name": "PhucNV", "focus_areas": ["RAG architecture", "Retrieval eval"]},
            {"name": "NgaLM", "focus_areas": ["Prompt engineering", "Safety"]},
            {"name": "VinhDT", "focus_areas": ["Model serving", "Inference optimization"]},
            {"name": "TamLT", "focus_areas": ["MLOps", "Experiment tracking"]},
            {"name": "ThuyHN", "focus_areas": ["Data annotation", "Evaluation"]},
            {"name": "KietPN", "focus_areas": ["Knowledge graphs", "Reasoning pipelines"]},
            {"name": "HaiPT", "focus_areas": ["NLP", "Vietnamese language quality"]},
        ],
        "case_studies": [
            {
                "title": "Internal Opportunity Matching Copilot",
                "domain": "Sales Enablement",
                "tech_stack": ["Python", "RAG", "ChromaDB", "LangChain"],
                "description": "Built matching assistant combining capability vectors and chat context.",
                "url": "https://example.internal/case/ai-matching-copilot",
            },
            {
                "title": "Contract Review Assistant",
                "domain": "Legal Tech",
                "tech_stack": ["LLM", "RAG", "Evaluation"],
                "description": "Automated clause risk highlighting with retrieval-backed citations.",
                "url": "https://example.internal/case/ai-contract-review",
            },
            {
                "title": "Support Ticket Triage Agent",
                "domain": "Customer Support",
                "tech_stack": ["Python", "LLM", "Vector Search"],
                "description": "Classified and routed tickets with confidence and fallback rules.",
                "url": "https://example.internal/case/ai-ticket-triage",
            },
            {
                "title": "Knowledge Bot for Delivery Teams",
                "domain": "Internal Productivity",
                "tech_stack": ["LangChain", "OpenRouter", "RAG"],
                "description": "Q&A bot over engineering playbooks and architecture documents.",
                "url": "https://example.internal/case/ai-knowledge-bot",
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
        mode = settings.chroma_mode.strip().lower()
        if mode == "persistent":
            persist_dir = Path(settings.chroma_persist_dir).expanduser().resolve()
            persist_dir.mkdir(parents=True, exist_ok=True)
            client = chromadb.PersistentClient(path=str(persist_dir))
        else:
            client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
        try:
            client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
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

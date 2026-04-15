import logging
import json
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.tools.vector_search import index_unit
from app.db.session import AsyncSessionLocal
from app.models.unit import Unit

logger = logging.getLogger(__name__)

def _build_case_study_text(unit: Unit) -> tuple[str, list[str]]:
    parts: list[str] = []
    titles: list[str] = []

    for cs in unit.case_studies:
        title = cs.title.strip()
        titles.append(title)

        seg: list[str] = [title]
        if cs.domain:
            seg.append(f"domain={cs.domain}")
        if cs.tech_stack:
            seg.append(f"tech={', '.join(cs.tech_stack)}")
        if cs.description:
            seg.append(cs.description.strip())
        parts.append(". ".join(seg))

    if unit.notes:
        parts.append(f"Unit notes: {unit.notes.strip()}")

    case_study_text = " | ".join(p for p in parts if p.strip())
    return case_study_text, titles


async def _reindex_with_session(session: AsyncSession, unit_uuid: UUID) -> bool:
    unit = await session.get(
        Unit,
        unit_uuid,
        options=[selectinload(Unit.experts), selectinload(Unit.case_studies)],
    )
    if not unit:
        logger.warning("reindex_unit skipped: unit not found (unit_id=%s)", unit_uuid)
        return False

    case_studies_text, case_study_titles = _build_case_study_text(unit)
    if not case_studies_text:
        case_studies_text = "No case studies yet."

    experts_list = [
        {
            "name": e.name,
            "focus_areas": e.focus_areas or [],
            "profile_url": str(e.profile_url) if e.profile_url else None,
        }
        for e in unit.experts
    ]
    case_studies_list = [
        {
            "title": cs.title,
            "domain": cs.domain,
            "tech_stack": cs.tech_stack or [],
            "url": str(getattr(cs, "url", None)) if getattr(cs, "url", None) else None,
        }
        for cs in unit.case_studies
    ]

    index_unit(
        unit_id=str(unit.id),
        unit_name=unit.name,
        tech_stack=unit.tech_stack or [],
        case_studies=case_studies_text,
        case_study_titles=case_study_titles,
        contact_name=unit.contact_name,
        contact_email=unit.contact_email or "",
        experts_json=json.dumps(experts_list),
        case_studies_json=json.dumps(case_studies_list),
    )
    return True


async def reindex_unit(unit_id: str, session: AsyncSession | None = None) -> None:
    """Sync one relational Unit record into the vector index."""
    try:
        unit_uuid = UUID(unit_id)
    except ValueError:
        logger.warning("reindex_unit skipped: invalid unit UUID '%s'", unit_id)
        return

    if session is not None:
        ok = await _reindex_with_session(session, unit_uuid)
    else:
        async with AsyncSessionLocal() as own_session:
            ok = await _reindex_with_session(own_session, unit_uuid)

    if ok:
        logger.info("Re-indexed unit into vector store (unit_id=%s)", unit_id)

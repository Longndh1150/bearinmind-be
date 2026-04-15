import logging

logger = logging.getLogger(__name__)

import json
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionLocal
from app.models.unit import Unit
from app.ai.tools.vector_search import index_unit

async def reindex_unit(unit_id: str) -> None:
    """
    Task D - Vector Reindex Hook
    Isolated module responsible for syncing relational capability states with ChromaDB.
    """
    logger.info(f"Triggering asynchronous vector re-indexing for unit: {unit_id}")
    
    async with AsyncSessionLocal() as session:
        unit = await session.get(
            Unit, 
            UUID(unit_id), 
            options=[selectinload(Unit.experts), selectinload(Unit.case_studies)]
        )
        if not unit:
            logger.warning(f"Unit {unit_id} not found in PostgreSQL during reindexing.")
            return

        tech_stack = unit.tech_stack or []
        case_studies = " ".join([f"{cs.title}. {cs.domain or ''}" for cs in unit.case_studies])
        case_study_titles = [cs.title for cs in unit.case_studies]
        
        experts_list = [{"name": e.name, "focus_areas": e.focus_areas or [], "profile_url": str(e.profile_url) if e.profile_url else None} for e in unit.experts]
        case_studies_list = [{"title": cs.title, "domain": cs.domain, "tech_stack": cs.tech_stack or [], "url": str(cs.url) if cs.url else None} for cs in unit.case_studies]

        index_unit(
            unit_id=str(unit.id),
            unit_name=unit.name,
            tech_stack=tech_stack,
            case_studies=case_studies,
            case_study_titles=case_study_titles,
            contact_name=unit.contact_name or "",
            contact_email=unit.contact_email or "",
            experts_json=json.dumps(experts_list),
            case_studies_json=json.dumps(case_studies_list),
        )
        logger.info(f"Unit {unit_id} reindexed into ChromaDB successfully.")

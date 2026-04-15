from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import require_active_user, require_superuser
from app.db.session import get_session
from app.models.user import User
from app.models.unit import Unit, UnitExpert, UnitCaseStudy
from app.schemas.unit import UnitCapabilitiesUpdate, UnitContact, UnitPublic, UnitCapabilities, UnitExpert as SchemaUnitExpert, UnitCaseStudy as SchemaUnitCaseStudy

from app.services.hrm_client import get_available_staff, get_unit_capacity
from app.services.case_study_client import get_case_studies
from app.services.unit_vector_indexer import reindex_unit

router = APIRouter(prefix="/units", tags=["units"])

def _to_unit_public(unit: Unit) -> UnitPublic:
    return UnitPublic(
        id=unit.id,
        code=unit.code,
        name=unit.name,
        status=unit.status,
        contact=UnitContact(
            name=unit.contact_name,
            email=unit.contact_email,
            title=unit.contact_title,
            phone=unit.contact_phone
        ),
        capabilities=UnitCapabilities(
            tech_stack=unit.tech_stack or [],
            experts=[SchemaUnitExpert(name=e.name, focus_areas=e.focus_areas or [], profile_url=e.profile_url) for e in unit.experts],
            case_studies=[SchemaUnitCaseStudy(title=c.title, domain=c.domain, tech_stack=c.tech_stack or [], url=c.url) for c in unit.case_studies],
            notes=unit.notes
        ),
        created_at=unit.created_at,
        updated_at=unit.updated_at,
    )

@router.get("", response_model=list[UnitPublic], summary="List units")
async def list_units(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_active_user)
) -> list[UnitPublic]:
    res = await session.execute(select(Unit).options(selectinload(Unit.experts), selectinload(Unit.case_studies)))
    return [_to_unit_public(u) for u in res.scalars().all()]


@router.get("/{unit_id}", response_model=UnitPublic, summary="Get unit by id")
async def get_unit(
    unit_id: UUID, 
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_active_user)
) -> UnitPublic:
    unit = await session.get(Unit, unit_id, options=[selectinload(Unit.experts), selectinload(Unit.case_studies)])
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    return _to_unit_public(unit)


@router.put("/{unit_id}/capabilities", response_model=UnitPublic, status_code=status.HTTP_200_OK, summary="Append to unit capabilities")
async def update_capabilities(
    unit_id: UUID,
    payload: UnitCapabilitiesUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_active_user),
) -> UnitPublic:
    unit = await session.get(Unit, unit_id, options=[selectinload(Unit.experts), selectinload(Unit.case_studies)])
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
        
    # Append tech stack
    existing_tech = unit.tech_stack or []
    new_tech = [t for t in payload.tech_stack if t not in existing_tech]
    unit.tech_stack = existing_tech + new_tech
    
    # Append experts based on uniqueness
    existing_expert_names = {e.name for e in unit.experts}
    for ex in payload.experts:
        if ex.name not in existing_expert_names:
            unit.experts.append(UnitExpert(name=ex.name, focus_areas=ex.focus_areas, profile_url=str(ex.profile_url) if ex.profile_url else None))
            
    # Append case studies based on uniqueness
    existing_cs_titles = {cs.title for cs in unit.case_studies}
    for cs in payload.case_studies:
        if cs.title not in existing_cs_titles:
            unit.case_studies.append(UnitCaseStudy(title=cs.title, domain=cs.domain, tech_stack=cs.tech_stack, url=str(cs.url) if cs.url else None))
            
    # Append notes
    if payload.notes:
        if unit.notes:
            unit.notes += f"\n{payload.notes}"
        else:
            unit.notes = payload.notes
            
    unit.capabilities_updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(unit)
    
    # Integrations & Reindexing hook
    await get_available_staff(str(unit_id))
    await get_unit_capacity(str(unit_id))
    await get_case_studies(str(unit_id))
    await reindex_unit(str(unit.id))
    
    return _to_unit_public(unit)

@router.delete("/{unit_id}/capabilities", status_code=status.HTTP_200_OK, summary="Clear particular or all capabilities")
async def clear_capabilities(
    unit_id: UUID,
    tech_to_remove: str | None = None,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_active_user)
):
    """
    Xóa capabilities của một unit. Nếu có tech_to_remove thì chỉ xóa mỗi công nghệ đó.
    """
    unit = await session.get(Unit, unit_id, options=[selectinload(Unit.experts), selectinload(Unit.case_studies)])
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
        
    if tech_to_remove:
        if unit.tech_stack and tech_to_remove in unit.tech_stack:
            unit.tech_stack = [t for t in unit.tech_stack if t != tech_to_remove]
        msg = f"Capability '{tech_to_remove}' cleared"
    else:
        unit.tech_stack = []
        # Clear relationships via SQLAlchemy
        for ex in list(unit.experts):
            await session.delete(ex)
        for cs in list(unit.case_studies):
            await session.delete(cs)
        unit.notes = None
        msg = "Capabilities cleared completely"
    
    unit.capabilities_updated_at = datetime.now(UTC)
    await session.commit()
    await reindex_unit(str(unit.id))
    
    return {"message": msg, "unit_id": unit_id}

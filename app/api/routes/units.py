from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.tools.vector_search import (
    search_units,
)
from app.api.deps import require_active_user
from app.db.session import get_session
from app.models.unit import Unit, UnitCaseStudy, UnitExpert
from app.models.user import User
from app.schemas.unit import (
    UnitCapabilities,
    UnitCapabilitiesUpdate,
    UnitCaseStudiesResponse,
    UnitContact,
    UnitPublic,
    UnitStaffAvailability,
)
from app.schemas.unit import UnitCaseStudy as SchemaUnitCaseStudy
from app.schemas.unit import UnitExpert as SchemaUnitExpert
from app.services.case_study_client import get_case_studies
from app.services.hrm_client import get_available_staff, get_unit_capacity
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
    query: str | None = None,
    limit: int = 10,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_active_user)
) -> list[UnitPublic]:
    if query:
        chroma_units = search_units(query, top_k=limit)
        if not chroma_units:
            return []
        
        unit_ids = []
        for u in chroma_units:
            try:
                unit_ids.append(UUID(u.unit_id))
            except ValueError:
                continue
                
        if not unit_ids:
            return []

        stmt = select(Unit).where(Unit.id.in_(unit_ids)).options(
            selectinload(Unit.experts), 
            selectinload(Unit.case_studies)
        )
        result = await session.execute(stmt)
        
        unit_map = {unit.id: unit for unit in result.scalars().all()}
        
        # return preserving chroma ranking
        return [_to_unit_public(unit_map[uid]) for uid in unit_ids if uid in unit_map]
    else:
        stmt = select(Unit).options(
            selectinload(Unit.experts), 
            selectinload(Unit.case_studies)
        ).limit(limit)
        result = await session.execute(stmt)
        return [_to_unit_public(u) for u in result.scalars().all()]


@router.get("/{unit_id}", response_model=UnitPublic, summary="Get unit by id")
async def get_unit(
    unit_id: UUID, 
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_active_user)
) -> UnitPublic:
    stmt = select(Unit).where(Unit.id == unit_id).options(
        selectinload(Unit.experts), 
        selectinload(Unit.case_studies)
    )
    result = await session.execute(stmt)
    unit = result.scalars().first()
    
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
    # Query unit from PG
    stmt = select(Unit).where(Unit.id == unit_id).options(
        selectinload(Unit.experts), 
        selectinload(Unit.case_studies)
    )
    result = await session.execute(stmt)
    unit = result.scalars().first()
    
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
        
    # Append tech stack
    existing_tech = unit.tech_stack or []
    new_tech = [t for t in payload.tech_stack if t not in existing_tech]
    unit.tech_stack = existing_tech + new_tech
    
    # Append experts
    existing_expert_names = {e.name for e in unit.experts}
    for ex in payload.experts:
        if ex.name not in existing_expert_names:
            new_exp = UnitExpert(
                unit_id=unit.id, 
                name=ex.name, 
                focus_areas=ex.focus_areas, 
                profile_url=str(ex.profile_url) if ex.profile_url else None
            )
            session.add(new_exp)
            unit.experts.append(new_exp)
            
    # Append case studies
    existing_cs_titles = {cs.title for cs in unit.case_studies}
    for cs in payload.case_studies:
        if cs.title not in existing_cs_titles:
            new_cs = UnitCaseStudy(
                unit_id=unit.id,
                title=cs.title,
                domain=cs.domain,
                tech_stack=cs.tech_stack,
                url=str(cs.url) if cs.url else None
            )
            session.add(new_cs)
            unit.case_studies.append(new_cs)
            
    await session.commit()
    await session.refresh(unit)
    
    # Reindex to Chroma
    await reindex_unit(str(unit_id), session=session)
    
    # Integrations
    await get_available_staff(str(unit_id))
    await get_unit_capacity(str(unit_id))
    await get_case_studies(str(unit_id))
    
    return _to_unit_public(unit)

@router.delete("/{unit_id}/capabilities", status_code=status.HTTP_200_OK, summary="Clear particular or all capabilities")
async def clear_capabilities(
    unit_id: UUID,
    tech_to_remove: str | None = None,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_active_user)
):
    stmt = select(Unit).where(Unit.id == unit_id).options(
        selectinload(Unit.experts), 
        selectinload(Unit.case_studies)
    )
    result = await session.execute(stmt)
    unit = result.scalars().first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
        
    if tech_to_remove:
        existing_tech = unit.tech_stack or []
        if tech_to_remove in existing_tech:
            unit.tech_stack = [t for t in existing_tech if t != tech_to_remove]
            await session.commit()
            await session.refresh(unit)
            await reindex_unit(str(unit_id), session=session)
        msg = f"Capability '{tech_to_remove}' cleared"
    else:
        unit.tech_stack = []
        for exp in list(unit.experts):
            await session.delete(exp)
        for cs in list(unit.case_studies):
            await session.delete(cs)
        await session.commit()
        await session.refresh(unit)
        await reindex_unit(str(unit_id), session=session)
        msg = "Capabilities cleared completely"
    
    return {"message": msg, "unit_id": unit_id}

@router.get("/{unit_id}/staff/available", response_model=UnitStaffAvailability, summary="Get available staff and experts for a unit")
async def get_unit_staff_availability(
    unit_id: UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_active_user)
) -> UnitStaffAvailability:
    stmt = select(Unit).where(Unit.id == unit_id).options(selectinload(Unit.experts))
    result = await session.execute(stmt)
    unit = result.scalars().first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
        
    experts = [SchemaUnitExpert(name=e.name, focus_areas=e.focus_areas or [], profile_url=e.profile_url) for e in unit.experts]
    
    # Get available staff from HRM
    hrm_staff = await get_available_staff(str(unit_id))
    hrm_capacity = await get_unit_capacity(str(unit_id))
    
    return UnitStaffAvailability(
        experts=experts,
        hrm_available_staff=hrm_staff,
        hrm_capacity=hrm_capacity
    )

@router.get("/{unit_id}/case-studies", response_model=UnitCaseStudiesResponse, summary="Get case studies for a unit")
async def get_unit_case_studies_api(
    unit_id: UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_active_user)
) -> UnitCaseStudiesResponse:
    stmt = select(Unit).where(Unit.id == unit_id).options(selectinload(Unit.case_studies))
    result = await session.execute(stmt)
    unit = result.scalars().first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    
    db_case_studies = [SchemaUnitCaseStudy(title=cs.title, domain=cs.domain, tech_stack=cs.tech_stack or [], url=cs.url) for cs in unit.case_studies]
    
    # Fetch from external integration
    external_case_studies = await get_case_studies(str(unit_id))
    
    return UnitCaseStudiesResponse(
        internal=db_case_studies,
        external=external_case_studies
    )

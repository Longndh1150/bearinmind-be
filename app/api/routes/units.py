from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, status

from app.api.deps import require_active_user, require_superuser
from app.models.user import User
from app.schemas.unit import UnitCapabilitiesUpdate, UnitContact, UnitPublic

router = APIRouter(prefix="/units", tags=["units"])


@router.get(
    "",
    response_model=list[UnitPublic],
    summary="List units",
    description="Useful for FE dropdowns and admin screens.",
)
async def list_units(_: User = Depends(require_active_user)) -> list[UnitPublic]:
    now = datetime.now(UTC)
    return [
        UnitPublic(
            id=uuid4(),
            code="D365",
            name="(stub) D365 Division",
            status="active",
            contact=UnitContact(name="(stub) Delivery Leader", email="leader@rikkeisoft.com"),
            capabilities=UnitCapabilitiesUpdate(tech_stack=["D365", "Power Platform"]),
            created_at=now,
            updated_at=now,
        )
    ]


@router.get(
    "/{unit_id}",
    response_model=UnitPublic,
    summary="Get unit by id",
)
async def get_unit(unit_id: UUID, _: User = Depends(require_active_user)) -> UnitPublic:
    now = datetime.now(UTC)
    return UnitPublic(
        id=unit_id,
        code="(stub)",
        name="(stub) Unit",
        status="active",
        contact=UnitContact(name="(stub) Contact"),
        capabilities=UnitCapabilitiesUpdate(),
        created_at=now,
        updated_at=now,
    )


@router.put(
    "/{unit_id}/capabilities",
    response_model=UnitPublic,
    status_code=status.HTTP_200_OK,
    summary="Update unit capabilities",
    description="US3: authenticated unit lead updates capability info; triggers re-embed later.",
)
async def update_capabilities(
    unit_id: UUID,
    payload: UnitCapabilitiesUpdate,
    _: User = Depends(require_superuser),
) -> UnitPublic:
    now = datetime.now(UTC)
    return UnitPublic(
        id=unit_id,
        code="(stub)",
        name="(stub) Unit",
        status="active",
        contact=UnitContact(name="(stub) Contact"),
        capabilities=payload,
        created_at=now,
        updated_at=now,
    )


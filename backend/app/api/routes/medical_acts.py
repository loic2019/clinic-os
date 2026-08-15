"""
GET    /api/medical-acts
POST   /api/medical-acts
GET    /api/medical-acts/{id}
PUT    /api/medical-acts/{id}
POST   /api/medical-acts/{id}/prices   add a new price history entry (never overwrites)
DELETE /api/medical-acts/{id}          deactivate, never a hard delete
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import require_permission
from app.schemas.medical_act import (
    MedicalActCreate,
    MedicalActListItem,
    MedicalActListResponse,
    MedicalActPriceCreate,
    MedicalActRead,
    MedicalActUpdate,
)
from app.services.medical_act_service import MedicalActService

router = APIRouter(prefix="/medical-acts")


@router.get("", response_model=None, dependencies=[Depends(require_permission("medical_acts.read"))])
async def list_medical_acts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    category: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
):
    service = MedicalActService(db)
    items, total = await service.list_acts(
        page=page, page_size=page_size, search=search, category=category, active_only=active_only
    )
    data = MedicalActListResponse(
        items=[MedicalActListItem.model_validate(a) for a in items],
        total=total,
        page=page,
        page_size=page_size,
    )
    return {"success": True, "data": data, "message": "OK"}


@router.post("", response_model=None, dependencies=[Depends(require_permission("medical_acts.create"))])
async def create_medical_act(payload: MedicalActCreate, db: AsyncSession = Depends(get_db)):
    service = MedicalActService(db)
    act = await service.create_act(payload)
    await db.commit()
    return {"success": True, "data": MedicalActRead.model_validate(act), "message": "Acte médical créé."}


@router.get(
    "/{act_id}", response_model=None, dependencies=[Depends(require_permission("medical_acts.read"))]
)
async def get_medical_act(act_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = MedicalActService(db)
    act = await service.get_act(act_id)
    return {"success": True, "data": MedicalActRead.model_validate(act), "message": "OK"}


@router.put(
    "/{act_id}", response_model=None, dependencies=[Depends(require_permission("medical_acts.update"))]
)
async def update_medical_act(act_id: uuid.UUID, payload: MedicalActUpdate, db: AsyncSession = Depends(get_db)):
    service = MedicalActService(db)
    act = await service.update_act(act_id, payload)
    await db.commit()
    return {"success": True, "data": MedicalActRead.model_validate(act), "message": "Acte médical mis à jour."}


@router.post(
    "/{act_id}/prices",
    response_model=None,
    dependencies=[Depends(require_permission("medical_acts.update"))],
)
async def add_medical_act_price(
    act_id: uuid.UUID, payload: MedicalActPriceCreate, db: AsyncSession = Depends(get_db)
):
    service = MedicalActService(db)
    act = await service.add_price(act_id, payload)
    await db.commit()
    return {
        "success": True,
        "data": MedicalActRead.model_validate(act),
        "message": "Nouveau prix enregistré (historique conservé).",
    }


@router.delete(
    "/{act_id}", response_model=None, dependencies=[Depends(require_permission("medical_acts.update"))]
)
async def deactivate_medical_act(act_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = MedicalActService(db)
    act = await service.deactivate_act(act_id)
    await db.commit()
    return {"success": True, "data": MedicalActRead.model_validate(act), "message": "Acte médical désactivé."}

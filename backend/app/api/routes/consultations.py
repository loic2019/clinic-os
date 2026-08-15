"""
GET  /api/consultations
POST /api/consultations
GET  /api/consultations/{id}
PUT  /api/consultations/{id}
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user, require_permission
from app.models.user import User
from app.schemas.consultation import (
    ConsultationCreate,
    ConsultationListItem,
    ConsultationListResponse,
    ConsultationRead,
    ConsultationUpdate,
)
from app.services.consultation_service import ConsultationService

router = APIRouter(prefix="/consultations")


@router.get("", response_model=None, dependencies=[Depends(require_permission("consultations.read"))])
async def list_consultations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    patient_id: uuid.UUID | None = Query(default=None),
    doctor_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    service = ConsultationService(db)
    items, total = await service.list_consultations(
        page=page, page_size=page_size, patient_id=patient_id, doctor_id=doctor_id
    )
    data = ConsultationListResponse(
        items=[ConsultationListItem.model_validate(c) for c in items],
        total=total,
        page=page,
        page_size=page_size,
    )
    return {"success": True, "data": data, "message": "OK"}


@router.post("", response_model=None, dependencies=[Depends(require_permission("consultations.create"))])
async def create_consultation(
    payload: ConsultationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = ConsultationService(db)
    consultation = await service.create_consultation(payload, created_by_id=current_user.id)
    await db.commit()
    return {
        "success": True,
        "data": ConsultationRead.model_validate(consultation),
        "message": f"Consultation {consultation.consultation_number} créée.",
    }


@router.get(
    "/{consultation_id}",
    response_model=None,
    dependencies=[Depends(require_permission("consultations.read"))],
)
async def get_consultation(consultation_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = ConsultationService(db)
    consultation = await service.get_consultation(consultation_id)
    return {"success": True, "data": ConsultationRead.model_validate(consultation), "message": "OK"}


@router.put(
    "/{consultation_id}",
    response_model=None,
    dependencies=[Depends(require_permission("consultations.update"))],
)
async def update_consultation(
    consultation_id: uuid.UUID, payload: ConsultationUpdate, db: AsyncSession = Depends(get_db)
):
    service = ConsultationService(db)
    consultation = await service.update_consultation(consultation_id, payload)
    await db.commit()
    return {
        "success": True,
        "data": ConsultationRead.model_validate(consultation),
        "message": "Consultation mise à jour.",
    }

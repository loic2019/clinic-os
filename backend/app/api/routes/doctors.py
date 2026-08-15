"""
GET    /api/doctors
POST   /api/doctors
GET    /api/doctors/{id}
PUT    /api/doctors/{id}
DELETE /api/doctors/{id}   (deactivate, never a hard delete)
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import require_permission
from app.schemas.doctor import DoctorCreate, DoctorListResponse, DoctorRead, DoctorUpdate
from app.services.doctor_service import DoctorService

router = APIRouter(prefix="/doctors")


@router.get("", response_model=None, dependencies=[Depends(require_permission("doctors.read"))])
async def list_doctors(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
):
    service = DoctorService(db)
    items, total = await service.list_doctors(
        page=page, page_size=page_size, search=search, active_only=active_only
    )
    data = DoctorListResponse(
        items=[DoctorRead.model_validate(d) for d in items], total=total, page=page, page_size=page_size
    )
    return {"success": True, "data": data, "message": "OK"}


@router.post("", response_model=None, dependencies=[Depends(require_permission("doctors.create"))])
async def create_doctor(payload: DoctorCreate, db: AsyncSession = Depends(get_db)):
    service = DoctorService(db)
    doctor = await service.create_doctor(payload)
    await db.commit()
    return {"success": True, "data": DoctorRead.model_validate(doctor), "message": "Médecin créé."}


@router.get("/{doctor_id}", response_model=None, dependencies=[Depends(require_permission("doctors.read"))])
async def get_doctor(doctor_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = DoctorService(db)
    doctor = await service.get_doctor(doctor_id)
    return {"success": True, "data": DoctorRead.model_validate(doctor), "message": "OK"}


@router.put("/{doctor_id}", response_model=None, dependencies=[Depends(require_permission("doctors.update"))])
async def update_doctor(doctor_id: uuid.UUID, payload: DoctorUpdate, db: AsyncSession = Depends(get_db)):
    service = DoctorService(db)
    doctor = await service.update_doctor(doctor_id, payload)
    await db.commit()
    return {"success": True, "data": DoctorRead.model_validate(doctor), "message": "Médecin mis à jour."}


@router.delete(
    "/{doctor_id}", response_model=None, dependencies=[Depends(require_permission("doctors.update"))]
)
async def deactivate_doctor(doctor_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = DoctorService(db)
    doctor = await service.deactivate_doctor(doctor_id)
    await db.commit()
    return {"success": True, "data": DoctorRead.model_validate(doctor), "message": "Médecin désactivé."}

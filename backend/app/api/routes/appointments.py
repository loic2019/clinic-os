"""
GET  /api/appointments
POST /api/appointments
GET  /api/appointments/{id}
PUT  /api/appointments/{id}
POST /api/appointments/{id}/cancel
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user, require_permission
from app.models.appointment import AppointmentStatus
from app.models.user import User
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentListResponse,
    AppointmentRead,
    AppointmentUpdate,
)
from app.services.appointment_service import AppointmentService

router = APIRouter(prefix="/appointments")


@router.get("", response_model=None, dependencies=[Depends(require_permission("appointments.read"))])
async def list_appointments(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    patient_id: uuid.UUID | None = Query(default=None),
    doctor_id: uuid.UUID | None = Query(default=None),
    status: AppointmentStatus | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    service = AppointmentService(db)
    items, total = await service.list_appointments(
        page=page,
        page_size=page_size,
        patient_id=patient_id,
        doctor_id=doctor_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
    )
    data = AppointmentListResponse(
        items=[AppointmentRead.model_validate(a) for a in items], total=total, page=page, page_size=page_size
    )
    return {"success": True, "data": data, "message": "OK"}


@router.post("", response_model=None, dependencies=[Depends(require_permission("appointments.create"))])
async def create_appointment(
    payload: AppointmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = AppointmentService(db)
    appointment = await service.create_appointment(payload, created_by_id=current_user.id)
    await db.commit()
    return {
        "success": True,
        "data": AppointmentRead.model_validate(appointment),
        "message": "Rendez-vous créé.",
    }


@router.get(
    "/{appointment_id}",
    response_model=None,
    dependencies=[Depends(require_permission("appointments.read"))],
)
async def get_appointment(appointment_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = AppointmentService(db)
    appointment = await service.get_appointment(appointment_id)
    return {"success": True, "data": AppointmentRead.model_validate(appointment), "message": "OK"}


@router.put(
    "/{appointment_id}",
    response_model=None,
    dependencies=[Depends(require_permission("appointments.update"))],
)
async def update_appointment(
    appointment_id: uuid.UUID, payload: AppointmentUpdate, db: AsyncSession = Depends(get_db)
):
    service = AppointmentService(db)
    appointment = await service.update_appointment(appointment_id, payload)
    await db.commit()
    return {
        "success": True,
        "data": AppointmentRead.model_validate(appointment),
        "message": "Rendez-vous mis à jour.",
    }


@router.post(
    "/{appointment_id}/cancel",
    response_model=None,
    dependencies=[Depends(require_permission("appointments.update"))],
)
async def cancel_appointment(appointment_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = AppointmentService(db)
    appointment = await service.cancel_appointment(appointment_id)
    await db.commit()
    return {
        "success": True,
        "data": AppointmentRead.model_validate(appointment),
        "message": "Rendez-vous annulé.",
    }

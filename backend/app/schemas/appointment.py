"""Pydantic schemas for /api/appointments."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.appointment import AppointmentStatus


class AppointmentCreate(BaseModel):
    patient_id: uuid.UUID
    doctor_id: uuid.UUID | None = None
    service: str | None = None
    scheduled_at: datetime
    duration_minutes: int = Field(default=30, gt=0, le=480)
    reason: str | None = None
    notes: str | None = None


class AppointmentUpdate(BaseModel):
    doctor_id: uuid.UUID | None = None
    service: str | None = None
    scheduled_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, gt=0, le=480)
    reason: str | None = None
    notes: str | None = None
    status: AppointmentStatus | None = None


class AppointmentRead(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    doctor_id: uuid.UUID | None
    service: str | None
    scheduled_at: datetime
    duration_minutes: int
    reason: str | None
    status: AppointmentStatus
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AppointmentListResponse(BaseModel):
    items: list[AppointmentRead]
    total: int
    page: int
    page_size: int

"""Data access layer for Appointment."""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment, AppointmentStatus


class AppointmentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, appointment_id: uuid.UUID) -> Appointment | None:
        result = await self.db.execute(select(Appointment).where(Appointment.id == appointment_id))
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        *,
        page: int,
        page_size: int,
        patient_id: uuid.UUID | None = None,
        doctor_id: uuid.UUID | None = None,
        status: AppointmentStatus | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[Appointment], int]:
        query = select(Appointment)
        count_query = select(func.count()).select_from(Appointment)

        if patient_id:
            query = query.where(Appointment.patient_id == patient_id)
            count_query = count_query.where(Appointment.patient_id == patient_id)
        if doctor_id:
            query = query.where(Appointment.doctor_id == doctor_id)
            count_query = count_query.where(Appointment.doctor_id == doctor_id)
        if status:
            query = query.where(Appointment.status == status)
            count_query = count_query.where(Appointment.status == status)
        if date_from:
            query = query.where(Appointment.scheduled_at >= date_from)
            count_query = count_query.where(Appointment.scheduled_at >= date_from)
        if date_to:
            query = query.where(Appointment.scheduled_at <= date_to)
            count_query = count_query.where(Appointment.scheduled_at <= date_to)

        total = (await self.db.execute(count_query)).scalar_one()
        query = query.order_by(Appointment.scheduled_at.asc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def has_conflict(
        self, doctor_id: uuid.UUID, scheduled_at: datetime, duration_minutes: int, *, exclude_id: uuid.UUID | None = None
    ) -> bool:
        """A doctor cannot have two overlapping non-cancelled appointments."""
        from datetime import timedelta

        end_time = scheduled_at + timedelta(minutes=duration_minutes)

        candidates_query = select(Appointment).where(
            Appointment.doctor_id == doctor_id,
            Appointment.status.notin_([AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW]),
            Appointment.scheduled_at < end_time,
        )
        if exclude_id:
            candidates_query = candidates_query.where(Appointment.id != exclude_id)

        candidates = (await self.db.execute(candidates_query)).scalars().all()
        for existing in candidates:
            existing_end = existing.scheduled_at + timedelta(minutes=existing.duration_minutes)
            if existing_end > scheduled_at:
                return True
        return False

    async def create(self, appointment: Appointment) -> Appointment:
        self.db.add(appointment)
        await self.db.flush()
        await self.db.refresh(appointment)
        return appointment

    async def save(self, appointment: Appointment) -> Appointment:
        await self.db.flush()
        await self.db.refresh(appointment)
        return appointment

"""Appointment business logic (spec section 41)."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.appointment import Appointment, AppointmentStatus
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.patient_repository import PatientRepository
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate


class AppointmentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.appointments = AppointmentRepository(db)
        self.patients = PatientRepository(db)

    async def create_appointment(
        self, payload: AppointmentCreate, *, created_by_id: uuid.UUID | None
    ) -> Appointment:
        patient = await self.patients.get_by_id(payload.patient_id, include_archived=False)
        if patient is None:
            raise NotFoundError("Patient introuvable.")

        if payload.doctor_id:
            conflict = await self.appointments.has_conflict(
                payload.doctor_id, payload.scheduled_at, payload.duration_minutes
            )
            if conflict:
                raise ConflictError("Ce médecin a déjà un rendez-vous sur ce créneau.")

        appointment = Appointment(
            patient_id=payload.patient_id,
            doctor_id=payload.doctor_id,
            service=payload.service,
            scheduled_at=payload.scheduled_at,
            duration_minutes=payload.duration_minutes,
            reason=payload.reason,
            notes=payload.notes,
            created_by_id=created_by_id,
        )
        return await self.appointments.create(appointment)

    async def get_appointment(self, appointment_id: uuid.UUID) -> Appointment:
        appointment = await self.appointments.get_by_id(appointment_id)
        if appointment is None:
            raise NotFoundError("Rendez-vous introuvable.")
        return appointment

    async def list_appointments(
        self,
        *,
        page: int,
        page_size: int,
        patient_id: uuid.UUID | None,
        doctor_id: uuid.UUID | None,
        status: AppointmentStatus | None,
        date_from,
        date_to,
    ):
        return await self.appointments.list_paginated(
            page=page,
            page_size=page_size,
            patient_id=patient_id,
            doctor_id=doctor_id,
            status=status,
            date_from=date_from,
            date_to=date_to,
        )

    async def update_appointment(
        self, appointment_id: uuid.UUID, payload: AppointmentUpdate
    ) -> Appointment:
        appointment = await self.get_appointment(appointment_id)
        update_data = payload.model_dump(exclude_unset=True)

        new_doctor_id = update_data.get("doctor_id", appointment.doctor_id)
        new_scheduled_at = update_data.get("scheduled_at", appointment.scheduled_at)
        new_duration = update_data.get("duration_minutes", appointment.duration_minutes)

        if new_doctor_id and ("scheduled_at" in update_data or "duration_minutes" in update_data or "doctor_id" in update_data):
            conflict = await self.appointments.has_conflict(
                new_doctor_id, new_scheduled_at, new_duration, exclude_id=appointment.id
            )
            if conflict:
                raise ConflictError("Ce médecin a déjà un rendez-vous sur ce créneau.")

        for field, value in update_data.items():
            setattr(appointment, field, value)

        return await self.appointments.save(appointment)

    async def cancel_appointment(self, appointment_id: uuid.UUID) -> Appointment:
        appointment = await self.get_appointment(appointment_id)
        appointment.status = AppointmentStatus.CANCELLED
        return await self.appointments.save(appointment)

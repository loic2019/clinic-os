"""Doctor management business logic."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.doctor import Doctor
from app.repositories.doctor_repository import DoctorRepository
from app.schemas.doctor import DoctorCreate, DoctorUpdate


class DoctorService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.doctors = DoctorRepository(db)

    async def create_doctor(self, payload: DoctorCreate) -> Doctor:
        doctor = Doctor(**payload.model_dump())
        return await self.doctors.create(doctor)

    async def get_doctor(self, doctor_id: uuid.UUID) -> Doctor:
        doctor = await self.doctors.get_by_id(doctor_id)
        if doctor is None:
            raise NotFoundError("Médecin introuvable.")
        return doctor

    async def list_doctors(self, *, page: int, page_size: int, search: str | None, active_only: bool):
        return await self.doctors.list_paginated(
            page=page, page_size=page_size, search=search, active_only=active_only
        )

    async def update_doctor(self, doctor_id: uuid.UUID, payload: DoctorUpdate) -> Doctor:
        doctor = await self.get_doctor(doctor_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(doctor, field, value)
        return await self.doctors.save(doctor)

    async def deactivate_doctor(self, doctor_id: uuid.UUID) -> Doctor:
        doctor = await self.get_doctor(doctor_id)
        doctor.is_active = False
        return await self.doctors.save(doctor)

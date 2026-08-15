"""Data access layer for Patient and its sub-resources."""

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.patient import (
    MedicalHistory,
    Patient,
    PatientAllergy,
    PatientContact,
    PatientInsurance,
)


class PatientRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, patient_id: uuid.UUID, *, include_archived: bool = True) -> Patient | None:
        query = select(Patient).where(Patient.id == patient_id)
        if not include_archived:
            query = query.where(Patient.deleted_at.is_(None))
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_number(self, patient_number: str) -> Patient | None:
        result = await self.db.execute(
            select(Patient).where(Patient.patient_number == patient_number)
        )
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None = None,
        gender: str | None = None,
        include_archived: bool = False,
    ) -> tuple[list[Patient], int]:
        query = select(Patient)
        count_query = select(func.count()).select_from(Patient)

        if not include_archived:
            query = query.where(Patient.deleted_at.is_(None))
            count_query = count_query.where(Patient.deleted_at.is_(None))

        if gender:
            query = query.where(Patient.gender == gender)
            count_query = count_query.where(Patient.gender == gender)

        if search:
            pattern = f"%{search}%"
            condition = or_(
                Patient.patient_number.ilike(pattern),
                Patient.first_name.ilike(pattern),
                Patient.last_name.ilike(pattern),
                Patient.phone.ilike(pattern),
                Patient.email.ilike(pattern),
            )
            query = query.where(condition)
            count_query = count_query.where(condition)

        total = (await self.db.execute(count_query)).scalar_one()

        query = query.order_by(Patient.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def create(self, patient: Patient) -> Patient:
        self.db.add(patient)
        await self.db.flush()
        await self.db.refresh(patient)
        return patient

    async def save(self, patient: Patient) -> Patient:
        await self.db.flush()
        await self.db.refresh(patient)
        return patient

    # --- Sub-resources ---------------------------------------------------

    async def get_contact(self, patient_id: uuid.UUID, contact_id: uuid.UUID) -> PatientContact | None:
        result = await self.db.execute(
            select(PatientContact).where(
                PatientContact.id == contact_id, PatientContact.patient_id == patient_id
            )
        )
        return result.scalar_one_or_none()

    async def get_insurance(self, patient_id: uuid.UUID, insurance_id: uuid.UUID) -> PatientInsurance | None:
        result = await self.db.execute(
            select(PatientInsurance).where(
                PatientInsurance.id == insurance_id, PatientInsurance.patient_id == patient_id
            )
        )
        return result.scalar_one_or_none()

    async def get_allergy(self, patient_id: uuid.UUID, allergy_id: uuid.UUID) -> PatientAllergy | None:
        result = await self.db.execute(
            select(PatientAllergy).where(
                PatientAllergy.id == allergy_id, PatientAllergy.patient_id == patient_id
            )
        )
        return result.scalar_one_or_none()

    async def get_medical_history(
        self, patient_id: uuid.UUID, history_id: uuid.UUID
    ) -> MedicalHistory | None:
        result = await self.db.execute(
            select(MedicalHistory).where(
                MedicalHistory.id == history_id, MedicalHistory.patient_id == patient_id
            )
        )
        return result.scalar_one_or_none()

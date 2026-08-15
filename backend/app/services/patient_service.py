"""Patient management business logic (spec sections 10-11)."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.patient import (
    MedicalHistory,
    Patient,
    PatientAllergy,
    PatientContact,
    PatientInsurance,
)
from app.repositories.patient_repository import PatientRepository
from app.schemas.patient import (
    MedicalHistoryCreate,
    PatientAllergyCreate,
    PatientContactCreate,
    PatientCreate,
    PatientInsuranceCreate,
    PatientUpdate,
)
from app.services.numbering_service import generate_number

PATIENT_NUMBER_KEY = "PAT"
PATIENT_NUMBER_PREFIX = "PAT"


class PatientService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.patients = PatientRepository(db)

    async def create_patient(self, payload: PatientCreate, *, created_by_id: uuid.UUID | None) -> Patient:
        patient_number = await generate_number(
            self.db, key=PATIENT_NUMBER_KEY, prefix=PATIENT_NUMBER_PREFIX
        )

        patient = Patient(
            patient_number=patient_number,
            first_name=payload.first_name,
            last_name=payload.last_name,
            date_of_birth=payload.date_of_birth,
            gender=payload.gender,
            phone=payload.phone,
            email=payload.email,
            address=payload.address,
            blood_group=payload.blood_group,
            observations=payload.observations,
            created_by_id=created_by_id,
            contacts=[PatientContact(**c.model_dump()) for c in payload.contacts],
            insurances=[PatientInsurance(**i.model_dump()) for i in payload.insurances],
            allergies=[PatientAllergy(**a.model_dump()) for a in payload.allergies],
            medical_histories=[MedicalHistory(**h.model_dump()) for h in payload.medical_histories],
        )
        return await self.patients.create(patient)

    async def get_patient(self, patient_id: uuid.UUID) -> Patient:
        patient = await self.patients.get_by_id(patient_id)
        if patient is None:
            raise NotFoundError("Patient introuvable.")
        return patient

    async def list_patients(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None,
        gender: str | None,
        include_archived: bool,
    ):
        return await self.patients.list_paginated(
            page=page, page_size=page_size, search=search, gender=gender, include_archived=include_archived
        )

    async def update_patient(self, patient_id: uuid.UUID, payload: PatientUpdate) -> Patient:
        patient = await self.get_patient(patient_id)

        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(patient, field, value)

        return await self.patients.save(patient)

    async def archive_patient(self, patient_id: uuid.UUID) -> Patient:
        from app.models.base import utcnow

        patient = await self.get_patient(patient_id)
        patient.deleted_at = utcnow()
        return await self.patients.save(patient)

    async def unarchive_patient(self, patient_id: uuid.UUID) -> Patient:
        patient = await self.get_patient(patient_id)
        patient.deleted_at = None
        return await self.patients.save(patient)

    # --- Sub-resources ---------------------------------------------------

    async def add_contact(self, patient_id: uuid.UUID, payload: PatientContactCreate) -> PatientContact:
        patient = await self.get_patient(patient_id)
        contact = PatientContact(patient_id=patient.id, **payload.model_dump())
        self.db.add(contact)
        await self.db.flush()
        await self.db.refresh(contact)
        return contact

    async def remove_contact(self, patient_id: uuid.UUID, contact_id: uuid.UUID) -> None:
        contact = await self.patients.get_contact(patient_id, contact_id)
        if contact is None:
            raise NotFoundError("Contact introuvable.")
        await self.db.delete(contact)
        await self.db.flush()

    async def add_insurance(self, patient_id: uuid.UUID, payload: PatientInsuranceCreate) -> PatientInsurance:
        patient = await self.get_patient(patient_id)
        insurance = PatientInsurance(patient_id=patient.id, **payload.model_dump())
        self.db.add(insurance)
        await self.db.flush()
        await self.db.refresh(insurance)
        return insurance

    async def remove_insurance(self, patient_id: uuid.UUID, insurance_id: uuid.UUID) -> None:
        insurance = await self.patients.get_insurance(patient_id, insurance_id)
        if insurance is None:
            raise NotFoundError("Assurance introuvable.")
        await self.db.delete(insurance)
        await self.db.flush()

    async def add_allergy(self, patient_id: uuid.UUID, payload: PatientAllergyCreate) -> PatientAllergy:
        patient = await self.get_patient(patient_id)
        allergy = PatientAllergy(patient_id=patient.id, **payload.model_dump())
        self.db.add(allergy)
        await self.db.flush()
        await self.db.refresh(allergy)
        return allergy

    async def remove_allergy(self, patient_id: uuid.UUID, allergy_id: uuid.UUID) -> None:
        allergy = await self.patients.get_allergy(patient_id, allergy_id)
        if allergy is None:
            raise NotFoundError("Allergie introuvable.")
        await self.db.delete(allergy)
        await self.db.flush()

    async def add_medical_history(
        self, patient_id: uuid.UUID, payload: MedicalHistoryCreate
    ) -> MedicalHistory:
        patient = await self.get_patient(patient_id)
        entry = MedicalHistory(patient_id=patient.id, **payload.model_dump())
        self.db.add(entry)
        await self.db.flush()
        await self.db.refresh(entry)
        return entry

    async def remove_medical_history(self, patient_id: uuid.UUID, history_id: uuid.UUID) -> None:
        entry = await self.patients.get_medical_history(patient_id, history_id)
        if entry is None:
            raise NotFoundError("Entrée d'antécédent introuvable.")
        await self.db.delete(entry)
        await self.db.flush()

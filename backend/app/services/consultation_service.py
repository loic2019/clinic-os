"""Consultation business logic (spec section 12)."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ClinicOSException, NotFoundError
from app.models.consultation import Consultation, ConsultationAct, Prescription, PrescriptionItem
from app.repositories.consultation_repository import ConsultationRepository
from app.repositories.medical_act_repository import MedicalActRepository
from app.repositories.patient_repository import PatientRepository
from app.schemas.consultation import ConsultationCreate, ConsultationUpdate
from app.services.numbering_service import generate_number

CONSULTATION_NUMBER_KEY = "CONS"
CONSULTATION_NUMBER_PREFIX = "CONS"


class ConsultationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.consultations = ConsultationRepository(db)
        self.medical_acts = MedicalActRepository(db)
        self.patients = PatientRepository(db)

    async def create_consultation(
        self, payload: ConsultationCreate, *, created_by_id: uuid.UUID | None
    ) -> Consultation:
        patient = await self.patients.get_by_id(payload.patient_id, include_archived=False)
        if patient is None:
            raise NotFoundError("Patient introuvable.")

        consultation_number = await generate_number(
            self.db, key=CONSULTATION_NUMBER_KEY, prefix=CONSULTATION_NUMBER_PREFIX
        )

        consultation = Consultation(
            consultation_number=consultation_number,
            patient_id=payload.patient_id,
            doctor_id=payload.doctor_id,
            created_by_id=created_by_id,
            symptoms=payload.symptoms,
            temperature_celsius=payload.temperature_celsius,
            blood_pressure_systolic=payload.blood_pressure_systolic,
            blood_pressure_diastolic=payload.blood_pressure_diastolic,
            heart_rate_bpm=payload.heart_rate_bpm,
            weight_kg=payload.weight_kg,
            height_cm=payload.height_cm,
            oxygen_saturation=payload.oxygen_saturation,
            clinical_exam=payload.clinical_exam,
            diagnosis=payload.diagnosis,
            recommendations=payload.recommendations,
        )

        # --- Linked medical acts: snapshot the CURRENT price at the moment
        # of the consultation (spec section 14) so later catalog price
        # changes never retroactively alter what was actually charged. ---
        for act_input in payload.acts:
            medical_act = await self.medical_acts.get_by_id(act_input.medical_act_id)
            if medical_act is None:
                raise NotFoundError(f"Acte médical introuvable : {act_input.medical_act_id}")
            current_price = medical_act.current_price
            if current_price is None:
                raise ClinicOSException(
                    f"L'acte '{medical_act.name}' n'a aucun prix en vigueur.", code="NO_PRICE"
                )
            consultation.acts.append(
                ConsultationAct(
                    medical_act_id=medical_act.id,
                    quantity=act_input.quantity,
                    unit_price_applied=current_price.price,
                    act_name_snapshot=medical_act.name,
                )
            )

        for prescription_input in payload.prescriptions:
            prescription = Prescription(
                patient_id=payload.patient_id,
                doctor_id=payload.doctor_id,
                notes=prescription_input.notes,
                items=[
                    PrescriptionItem(**item.model_dump()) for item in prescription_input.items
                ],
            )
            consultation.prescriptions.append(prescription)

        created = await self.consultations.create(consultation)
        # Re-fetch rather than relying on the just-flushed in-memory graph:
        # session.refresh() on the parent does not reliably keep nested
        # selectin-loaded collections (like prescriptions[].items) usable
        # under AsyncSession — a clean query avoids any lazy-load surprises.
        return await self.consultations.get_by_id(created.id)

    async def get_consultation(self, consultation_id: uuid.UUID) -> Consultation:
        consultation = await self.consultations.get_by_id(consultation_id)
        if consultation is None:
            raise NotFoundError("Consultation introuvable.")
        return consultation

    async def list_consultations(
        self, *, page: int, page_size: int, patient_id: uuid.UUID | None, doctor_id: uuid.UUID | None
    ):
        return await self.consultations.list_paginated(
            page=page, page_size=page_size, patient_id=patient_id, doctor_id=doctor_id
        )

    async def update_consultation(
        self, consultation_id: uuid.UUID, payload: ConsultationUpdate
    ) -> Consultation:
        consultation = await self.get_consultation(consultation_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(consultation, field, value)
        return await self.consultations.save(consultation)

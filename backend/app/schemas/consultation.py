"""Pydantic schemas for /api/consultations."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ConsultationActInput(BaseModel):
    medical_act_id: uuid.UUID
    quantity: int = Field(default=1, gt=0)


class ConsultationActRead(BaseModel):
    id: uuid.UUID
    medical_act_id: uuid.UUID
    act_name_snapshot: str
    quantity: int
    unit_price_applied: float

    model_config = {"from_attributes": True}


class PrescriptionItemInput(BaseModel):
    medication_name: str = Field(..., min_length=1, max_length=255)
    dosage: str | None = None
    frequency: str | None = None
    duration: str | None = None
    instructions: str | None = None


class PrescriptionItemRead(PrescriptionItemInput):
    id: uuid.UUID
    model_config = {"from_attributes": True}


class PrescriptionInput(BaseModel):
    notes: str | None = None
    items: list[PrescriptionItemInput] = Field(default_factory=list, min_length=1)


class PrescriptionRead(BaseModel):
    id: uuid.UUID
    notes: str | None
    items: list[PrescriptionItemRead]
    created_at: datetime

    model_config = {"from_attributes": True}


class ConsultationCreate(BaseModel):
    patient_id: uuid.UUID
    doctor_id: uuid.UUID | None = None

    symptoms: str | None = None
    temperature_celsius: float | None = Field(default=None, ge=25, le=45)
    blood_pressure_systolic: int | None = Field(default=None, gt=0, lt=350)
    blood_pressure_diastolic: int | None = Field(default=None, gt=0, lt=250)
    heart_rate_bpm: int | None = Field(default=None, gt=0, lt=350)
    weight_kg: float | None = Field(default=None, gt=0, lt=500)
    height_cm: float | None = Field(default=None, gt=0, lt=300)
    oxygen_saturation: float | None = Field(default=None, ge=0, le=100)

    clinical_exam: str | None = None
    diagnosis: str | None = None
    recommendations: str | None = None

    acts: list[ConsultationActInput] = Field(default_factory=list)
    prescriptions: list[PrescriptionInput] = Field(default_factory=list)


class ConsultationUpdate(BaseModel):
    symptoms: str | None = None
    temperature_celsius: float | None = Field(default=None, ge=25, le=45)
    blood_pressure_systolic: int | None = Field(default=None, gt=0, lt=350)
    blood_pressure_diastolic: int | None = Field(default=None, gt=0, lt=250)
    heart_rate_bpm: int | None = Field(default=None, gt=0, lt=350)
    weight_kg: float | None = Field(default=None, gt=0, lt=500)
    height_cm: float | None = Field(default=None, gt=0, lt=300)
    oxygen_saturation: float | None = Field(default=None, ge=0, le=100)
    clinical_exam: str | None = None
    diagnosis: str | None = None
    recommendations: str | None = None


class ConsultationListItem(BaseModel):
    id: uuid.UUID
    consultation_number: str
    patient_id: uuid.UUID
    doctor_id: uuid.UUID | None
    diagnosis: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConsultationRead(ConsultationListItem):
    symptoms: str | None
    temperature_celsius: float | None
    blood_pressure_systolic: int | None
    blood_pressure_diastolic: int | None
    heart_rate_bpm: int | None
    weight_kg: float | None
    height_cm: float | None
    oxygen_saturation: float | None
    bmi: float | None
    clinical_exam: str | None
    recommendations: str | None
    acts: list[ConsultationActRead]
    prescriptions: list[PrescriptionRead]


class ConsultationListResponse(BaseModel):
    items: list[ConsultationListItem]
    total: int
    page: int
    page_size: int

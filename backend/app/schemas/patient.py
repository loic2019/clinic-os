"""Pydantic schemas for /api/patients and its sub-resources."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.patient import BloodGroup, Gender

# --- Sub-resources -----------------------------------------------------


class PatientContactCreate(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    relationship_label: str | None = Field(default=None, max_length=64, examples=["Époux(se)"])
    phone: str | None = None
    email: EmailStr | None = None


class PatientContactRead(PatientContactCreate):
    id: uuid.UUID
    model_config = {"from_attributes": True}


class PatientInsuranceCreate(BaseModel):
    insurance_name: str = Field(..., min_length=1, max_length=255)
    insurance_number: str | None = None
    is_primary: bool = False


class PatientInsuranceRead(PatientInsuranceCreate):
    id: uuid.UUID
    model_config = {"from_attributes": True}


class PatientAllergyCreate(BaseModel):
    allergen: str = Field(..., min_length=1, max_length=255)
    severity: str | None = Field(default=None, examples=["légère", "modérée", "sévère"])
    notes: str | None = None


class PatientAllergyRead(PatientAllergyCreate):
    id: uuid.UUID
    model_config = {"from_attributes": True}


class MedicalHistoryCreate(BaseModel):
    condition: str = Field(..., min_length=1, max_length=255)
    notes: str | None = None
    recorded_on: date | None = None


class MedicalHistoryRead(MedicalHistoryCreate):
    id: uuid.UUID
    model_config = {"from_attributes": True}


# --- Patient -------------------------------------------------------------


class PatientCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=128)
    last_name: str = Field(..., min_length=1, max_length=128)
    date_of_birth: date | None = None
    gender: Gender | None = None
    phone: str | None = None
    email: EmailStr | None = None
    address: str | None = None
    blood_group: BloodGroup | None = None
    observations: str | None = None

    contacts: list[PatientContactCreate] = Field(default_factory=list)
    insurances: list[PatientInsuranceCreate] = Field(default_factory=list)
    allergies: list[PatientAllergyCreate] = Field(default_factory=list)
    medical_histories: list[MedicalHistoryCreate] = Field(default_factory=list)


class PatientUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=128)
    last_name: str | None = Field(default=None, min_length=1, max_length=128)
    date_of_birth: date | None = None
    gender: Gender | None = None
    phone: str | None = None
    email: EmailStr | None = None
    address: str | None = None
    blood_group: BloodGroup | None = None
    observations: str | None = None


class PatientListItem(BaseModel):
    id: uuid.UUID
    patient_number: str
    first_name: str
    last_name: str
    date_of_birth: date | None
    gender: Gender | None
    phone: str | None
    email: str | None
    created_at: datetime
    is_archived: bool = Field(validation_alias="is_deleted")

    model_config = {"from_attributes": True, "populate_by_name": True}


class PatientRead(PatientListItem):
    address: str | None
    blood_group: BloodGroup | None
    observations: str | None
    contacts: list[PatientContactRead]
    insurances: list[PatientInsuranceRead]
    allergies: list[PatientAllergyRead]
    medical_histories: list[MedicalHistoryRead]


class PatientListResponse(BaseModel):
    items: list[PatientListItem]
    total: int
    page: int
    page_size: int

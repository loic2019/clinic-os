"""Pydantic schemas for /api/doctors."""

import uuid

from pydantic import BaseModel, EmailStr, Field


class DoctorCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=128)
    last_name: str = Field(..., min_length=1, max_length=128)
    specialty: str | None = None
    license_number: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    user_id: uuid.UUID | None = Field(default=None, description="Optional linked login account")


class DoctorUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=128)
    last_name: str | None = Field(default=None, min_length=1, max_length=128)
    specialty: str | None = None
    license_number: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    is_active: bool | None = None


class DoctorRead(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    specialty: str | None
    license_number: str | None
    phone: str | None
    email: str | None
    is_active: bool

    model_config = {"from_attributes": True}


class DoctorListResponse(BaseModel):
    items: list[DoctorRead]
    total: int
    page: int
    page_size: int

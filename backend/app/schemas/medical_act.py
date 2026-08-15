"""Pydantic schemas for /api/medical-acts."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


class MedicalActPriceCreate(BaseModel):
    price: float = Field(..., gt=0)
    effective_from: date | None = Field(
        default=None, description="Defaults to today if omitted."
    )


class MedicalActPriceRead(BaseModel):
    id: uuid.UUID
    price: float
    effective_from: date
    created_at: datetime

    model_config = {"from_attributes": True}


class MedicalActCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=32, examples=["CONS-001"])
    name: str = Field(..., min_length=1, max_length=255, examples=["Consultation générale"])
    category: str = Field(..., min_length=1, max_length=64, examples=["Consultation"])
    description: str | None = None
    tax_rate: float = Field(default=0, ge=0, le=100)
    service: str | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    initial_price: float = Field(..., gt=0, description="Creates the first price history entry.")


class MedicalActUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, min_length=1, max_length=64)
    description: str | None = None
    tax_rate: float | None = Field(default=None, ge=0, le=100)
    service: str | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    is_active: bool | None = None


class MedicalActRead(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    category: str
    description: str | None
    tax_rate: float
    service: str | None
    duration_minutes: int | None
    is_active: bool
    current_price: float | None
    price_history: list[MedicalActPriceRead] = Field(validation_alias="prices")

    model_config = {"from_attributes": True, "populate_by_name": True}

    @field_validator("current_price", mode="before")
    @classmethod
    def extract_price_value(cls, value):
        if value is None:
            return None
        if hasattr(value, "price"):
            return value.price
        return value


class MedicalActListItem(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    category: str
    is_active: bool
    current_price: float | None

    model_config = {"from_attributes": True}

    @field_validator("current_price", mode="before")
    @classmethod
    def extract_price_value(cls, value):
        if value is None:
            return None
        if hasattr(value, "price"):
            return value.price
        return value


class MedicalActListResponse(BaseModel):
    items: list[MedicalActListItem]
    total: int
    page: int
    page_size: int

"""Pydantic schemas for /api/laboratory."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.laboratory import LabItemStatus, LabOrderStatus, SampleType

# --- Catalog -------------------------------------------------------------


class LabTestCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=32, examples=["LAB-001"])
    name: str = Field(..., min_length=1, max_length=255, examples=["NFS"])
    category: str = Field(..., min_length=1, max_length=64, examples=["Hématologie"])
    unit: str | None = None
    reference_range_low: float | None = None
    reference_range_high: float | None = None
    reference_range_text: str | None = None


class LabTestUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, min_length=1, max_length=64)
    unit: str | None = None
    reference_range_low: float | None = None
    reference_range_high: float | None = None
    reference_range_text: str | None = None
    is_active: bool | None = None


class LabTestRead(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    category: str
    unit: str | None
    reference_range_low: float | None
    reference_range_high: float | None
    reference_range_text: str | None
    is_active: bool

    model_config = {"from_attributes": True}


class LabTestListResponse(BaseModel):
    items: list[LabTestRead]
    total: int
    page: int
    page_size: int


# --- Results ---------------------------------------------------------------


class LabResultInput(BaseModel):
    value_numeric: float | None = None
    value_text: str | None = None
    notes: str | None = None


class LabResultRead(BaseModel):
    id: uuid.UUID
    value_numeric: float | None
    value_text: str | None
    unit: str | None
    reference_range_display: str | None
    is_abnormal: bool
    notes: str | None
    entered_at: datetime | None
    validated_at: datetime | None

    model_config = {"from_attributes": True}


# --- Order items -----------------------------------------------------------


class LabOrderItemRead(BaseModel):
    id: uuid.UUID
    lab_test_id: uuid.UUID
    test_name_snapshot: str
    status: LabItemStatus
    result: LabResultRead | None

    model_config = {"from_attributes": True}


# --- Samples ---------------------------------------------------------------


class LabSampleCreate(BaseModel):
    sample_type: SampleType
    collected_at: datetime | None = Field(default=None, description="Defaults to now if omitted.")
    notes: str | None = None


class LabSampleRead(BaseModel):
    id: uuid.UUID
    sample_type: SampleType
    collected_at: datetime
    notes: str | None

    model_config = {"from_attributes": True}


# --- Orders ------------------------------------------------------------------


class LabOrderCreate(BaseModel):
    patient_id: uuid.UUID
    doctor_id: uuid.UUID | None = None
    consultation_id: uuid.UUID | None = None
    notes: str | None = None
    lab_test_ids: list[uuid.UUID] = Field(..., min_length=1)


class LabOrderListItem(BaseModel):
    id: uuid.UUID
    order_number: str
    patient_id: uuid.UUID
    doctor_id: uuid.UUID | None
    status: LabOrderStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class LabOrderRead(LabOrderListItem):
    notes: str | None
    items: list[LabOrderItemRead]
    samples: list[LabSampleRead]


class LabOrderListResponse(BaseModel):
    items: list[LabOrderListItem]
    total: int
    page: int
    page_size: int

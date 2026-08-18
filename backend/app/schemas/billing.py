"""Pydantic schemas for /api/invoices."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.billing import CancellationStatus, InvoiceItemType, InvoiceStatus


class InvoiceItemInput(BaseModel):
    item_type: InvoiceItemType
    medical_act_id: uuid.UUID | None = Field(
        default=None, description="If set, description/price/tax are snapshotted from the catalog."
    )
    description: str | None = Field(
        default=None, description="Required if medical_act_id is not set (free-form line item)."
    )
    quantity: int = Field(default=1, gt=0)
    unit_price: float | None = Field(
        default=None, gt=0, description="Required if medical_act_id is not set."
    )


class InvoiceItemRead(BaseModel):
    id: uuid.UUID
    item_type: InvoiceItemType
    medical_act_id: uuid.UUID | None
    description: str
    quantity: int
    unit_price: float
    tax_rate: float
    line_total: float

    model_config = {"from_attributes": True}


class InvoiceCreate(BaseModel):
    patient_id: uuid.UUID
    discount_amount: float = Field(default=0, ge=0)
    notes: str | None = None
    items: list[InvoiceItemInput] = Field(..., min_length=1)


class InvoiceListItem(BaseModel):
    id: uuid.UUID
    invoice_number: str
    patient_id: uuid.UUID
    status: InvoiceStatus
    total: float
    amount_paid: float
    balance_due: float
    created_at: datetime
    created_by_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class InvoiceRead(InvoiceListItem):
    subtotal: float
    discount_amount: float
    notes: str | None
    items: list[InvoiceItemRead]


class InvoiceListResponse(BaseModel):
    items: list[InvoiceListItem]
    total: int
    page: int
    page_size: int


class CancellationRequestCreate(BaseModel):
    reason: str = Field(..., min_length=1)


class CancellationRequestReview(BaseModel):
    approve: bool
    review_notes: str | None = None


class CancellationRequestRead(BaseModel):
    id: uuid.UUID
    invoice_id: uuid.UUID
    reason: str
    status: CancellationStatus
    reviewed_at: datetime | None
    review_notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}

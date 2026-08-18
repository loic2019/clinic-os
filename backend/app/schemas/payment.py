"""Pydantic schemas for /api/payments."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.payment import PaymentMethod, PaymentStatus, RefundStatus


class PaymentCreate(BaseModel):
    invoice_id: uuid.UUID
    method: PaymentMethod
    amount: float = Field(..., gt=0)
    reference: str | None = None


class PaymentRead(BaseModel):
    id: uuid.UUID
    payment_number: str
    invoice_id: uuid.UUID
    patient_id: uuid.UUID
    cashier_id: uuid.UUID | None
    method: PaymentMethod
    amount: float
    reference: str | None
    status: PaymentStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class PaymentListResponse(BaseModel):
    items: list[PaymentRead]
    total: int
    page: int
    page_size: int


class RefundRequestCreate(BaseModel):
    amount: float = Field(..., gt=0)
    reason: str = Field(..., min_length=1)


class RefundRequestReview(BaseModel):
    approve: bool
    review_notes: str | None = None


class RefundRequestRead(BaseModel):
    id: uuid.UUID
    payment_id: uuid.UUID
    amount: float
    reason: str
    status: RefundStatus
    reviewed_at: datetime | None
    review_notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}

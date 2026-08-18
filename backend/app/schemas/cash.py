"""Pydantic schemas for /api/cash."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.cash import CashSessionStatus


class CashRegisterRead(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    is_active: bool

    model_config = {"from_attributes": True}


class CashSessionOpen(BaseModel):
    cash_register_id: uuid.UUID
    opening_balance: float = Field(..., ge=0)


class CashSessionClose(BaseModel):
    closing_balance: float = Field(..., ge=0, description="Actual counted amount.")
    difference_justification: str | None = Field(
        default=None, description="Required if closing_balance differs from the expected total."
    )


class CashSessionRead(BaseModel):
    id: uuid.UUID
    cash_register_id: uuid.UUID
    cashier_id: uuid.UUID | None
    opened_at: datetime
    opening_balance: float
    closed_at: datetime | None
    closing_balance: float | None
    expected_balance: float | None
    difference: float | None
    difference_justification: str | None
    status: CashSessionStatus

    model_config = {"from_attributes": True}


class CashSessionListResponse(BaseModel):
    items: list[CashSessionRead]
    total: int
    page: int
    page_size: int

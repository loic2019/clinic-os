"""Pydantic schemas for /api/accounting."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.accounting import AccountType


class AccountRead(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    account_type: AccountType
    is_active: bool

    model_config = {"from_attributes": True}


class AccountingLineRead(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    debit: float
    credit: float
    description: str | None

    model_config = {"from_attributes": True}


class AccountingEntryRead(BaseModel):
    id: uuid.UUID
    entry_number: str
    entry_date: date
    description: str
    source_type: str
    total_debit: float
    total_credit: float
    lines: list[AccountingLineRead]
    created_at: datetime

    model_config = {"from_attributes": True}


class AccountingEntryListResponse(BaseModel):
    items: list[AccountingEntryRead]
    total: int
    page: int
    page_size: int


class ExpenseCreate(BaseModel):
    category: str = Field(..., min_length=1, max_length=64, examples=["Loyer", "Fournitures", "Salaires"])
    description: str = Field(..., min_length=1, max_length=255)
    amount: float = Field(..., gt=0)
    expense_date: date | None = Field(default=None, description="Defaults to today if omitted.")


class ExpenseRead(BaseModel):
    id: uuid.UUID
    expense_number: str
    category: str
    description: str
    amount: float
    expense_date: date
    created_at: datetime

    model_config = {"from_attributes": True}


class ExpenseListResponse(BaseModel):
    items: list[ExpenseRead]
    total: int
    page: int
    page_size: int


class AccountingSummary(BaseModel):
    date_from: date
    date_to: date
    total_revenue: float
    total_expense: float
    net_result: float
    cash_balance: float

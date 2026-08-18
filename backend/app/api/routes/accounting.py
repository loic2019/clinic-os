"""
GET  /api/accounting/accounts                 chart of accounts
GET  /api/accounting/entries                    list accounting entries
GET  /api/accounting/entries/{id}
GET  /api/accounting/expenses                   list expenses
POST /api/accounting/expenses                    log an expense (auto-generates its entry)
GET  /api/accounting/summary                    revenue/expense/net/cash-balance report
"""

import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user, require_permission
from app.models.user import User
from app.schemas.accounting import (
    AccountingEntryListResponse,
    AccountingEntryRead,
    AccountRead,
    AccountingSummary,
    ExpenseCreate,
    ExpenseListResponse,
    ExpenseRead,
)
from app.services.accounting_service import AccountingService

router = APIRouter(prefix="/accounting")


@router.get("/accounts", response_model=None, dependencies=[Depends(require_permission("accounting.read"))])
async def list_accounts(db: AsyncSession = Depends(get_db)):
    service = AccountingService(db)
    accounts = await service.list_accounts()
    return {"success": True, "data": [AccountRead.model_validate(a) for a in accounts], "message": "OK"}


@router.get("/entries", response_model=None, dependencies=[Depends(require_permission("accounting.read"))])
async def list_entries(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    service = AccountingService(db)
    items, total = await service.list_entries(page=page, page_size=page_size, date_from=date_from, date_to=date_to)
    data = AccountingEntryListResponse(
        items=[AccountingEntryRead.model_validate(e) for e in items], total=total, page=page, page_size=page_size
    )
    return {"success": True, "data": data, "message": "OK"}


@router.get("/entries/{entry_id}", response_model=None, dependencies=[Depends(require_permission("accounting.read"))])
async def get_entry(entry_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = AccountingService(db)
    entry = await service.get_entry(entry_id)
    return {"success": True, "data": AccountingEntryRead.model_validate(entry), "message": "OK"}


@router.get("/expenses", response_model=None, dependencies=[Depends(require_permission("accounting.read"))])
async def list_expenses(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    service = AccountingService(db)
    items, total = await service.list_expenses(page=page, page_size=page_size, date_from=date_from, date_to=date_to)
    data = ExpenseListResponse(
        items=[ExpenseRead.model_validate(e) for e in items], total=total, page=page, page_size=page_size
    )
    return {"success": True, "data": data, "message": "OK"}


@router.post("/expenses", response_model=None, dependencies=[Depends(require_permission("accounting.create"))])
async def create_expense(
    payload: ExpenseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = AccountingService(db)
    expense = await service.create_expense(payload, created_by_id=current_user.id)
    await db.commit()
    return {
        "success": True,
        "data": ExpenseRead.model_validate(expense),
        "message": f"Dépense {expense.expense_number} enregistrée.",
    }


@router.get("/summary", response_model=None, dependencies=[Depends(require_permission("accounting.read"))])
async def get_summary(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    service = AccountingService(db)
    effective_to = date_to or date.today()
    effective_from = date_from or (effective_to - timedelta(days=30))
    summary = await service.get_summary(date_from=effective_from, date_to=effective_to)
    return {"success": True, "data": summary, "message": "OK"}

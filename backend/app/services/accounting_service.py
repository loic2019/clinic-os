"""Accounting business logic (spec section 35)."""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ClinicOSException, NotFoundError
from app.models.accounting import AccountingEntry, AccountingLine, AccountType, Expense
from app.repositories.accounting_repository import AccountingRepository
from app.schemas.accounting import AccountingSummary, ExpenseCreate
from app.services.numbering_service import generate_number

ENTRY_NUMBER_KEY = "ECR"
ENTRY_NUMBER_PREFIX = "ECR"
EXPENSE_NUMBER_KEY = "DEP"
EXPENSE_NUMBER_PREFIX = "DEP"

# Default chart of accounts (seeded — see database/seed.py). Referenced
# by code here so automatic entries never depend on a lookup that could
# silently fail if someone renames an account.
ACCOUNT_CASH = "512"
ACCOUNT_REVENUE = "706"
ACCOUNT_EXPENSE = "606"


class AccountingService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.accounting = AccountingRepository(db)

    async def list_accounts(self):
        return await self.accounting.list_accounts()

    async def create_balanced_entry(
        self,
        *,
        entry_date: date,
        description: str,
        source_type: str,
        source_id: uuid.UUID | None,
        lines: list[tuple[str, float, float, str | None]],
        created_by_id: uuid.UUID | None,
    ) -> AccountingEntry:
        """lines: list of (account_code, debit, credit, line_description).
        Raises if the entry does not balance — an accounting entry that
        doesn't balance is a bug, not a valid state (spec section 35)."""
        total_debit = round(sum(d for _, d, _, _ in lines), 2)
        total_credit = round(sum(c for _, _, c, _ in lines), 2)
        if total_debit != total_credit:
            raise ClinicOSException(
                f"Écriture déséquilibrée : débit={total_debit} crédit={total_credit}.",
                code="UNBALANCED_ENTRY",
            )

        entry_number = await generate_number(self.db, key=ENTRY_NUMBER_KEY, prefix=ENTRY_NUMBER_PREFIX)
        entry = AccountingEntry(
            entry_number=entry_number,
            entry_date=entry_date,
            description=description,
            source_type=source_type,
            source_id=source_id,
            created_by_id=created_by_id,
        )

        for account_code, debit, credit, line_description in lines:
            account = await self.accounting.get_account_by_code(account_code)
            if account is None:
                raise NotFoundError(f"Compte comptable introuvable : {account_code}")
            entry.lines.append(
                AccountingLine(account_id=account.id, debit=debit, credit=credit, description=line_description)
            )

        return await self.accounting.create_entry(entry)

    async def record_payment_entry(
        self, *, payment_id: uuid.UUID, amount: float, description: str, created_by_id: uuid.UUID | None
    ) -> AccountingEntry:
        """DEBIT Caisse / CREDIT Recettes médicales — spec section 35's example."""
        return await self.create_balanced_entry(
            entry_date=datetime.now(timezone.utc).date(),
            description=description,
            source_type="PAYMENT",
            source_id=payment_id,
            lines=[
                (ACCOUNT_CASH, amount, 0, "Encaissement"),
                (ACCOUNT_REVENUE, 0, amount, "Recette médicale"),
            ],
            created_by_id=created_by_id,
        )

    async def record_refund_entry(
        self, *, payment_id: uuid.UUID, amount: float, description: str, created_by_id: uuid.UUID | None
    ) -> AccountingEntry:
        """Reverses a payment entry: DEBIT Recettes / CREDIT Caisse."""
        return await self.create_balanced_entry(
            entry_date=datetime.now(timezone.utc).date(),
            description=description,
            source_type="REFUND",
            source_id=payment_id,
            lines=[
                (ACCOUNT_REVENUE, amount, 0, "Annulation recette (remboursement)"),
                (ACCOUNT_CASH, 0, amount, "Remboursement"),
            ],
            created_by_id=created_by_id,
        )

    async def get_entry(self, entry_id: uuid.UUID) -> AccountingEntry:
        entry = await self.accounting.get_entry_by_id(entry_id)
        if entry is None:
            raise NotFoundError("Écriture comptable introuvable.")
        return entry

    async def list_entries(self, *, page: int, page_size: int, date_from: date | None, date_to: date | None):
        return await self.accounting.list_entries_paginated(
            page=page, page_size=page_size, date_from=date_from, date_to=date_to
        )

    async def create_expense(self, payload: ExpenseCreate, *, created_by_id: uuid.UUID | None) -> Expense:
        expense_number = await generate_number(self.db, key=EXPENSE_NUMBER_KEY, prefix=EXPENSE_NUMBER_PREFIX)
        expense_date = payload.expense_date or datetime.now(timezone.utc).date()

        expense = Expense(
            expense_number=expense_number,
            category=payload.category,
            description=payload.description,
            amount=payload.amount,
            expense_date=expense_date,
            created_by_id=created_by_id,
        )
        created = await self.accounting.create_expense(expense)

        entry = await self.create_balanced_entry(
            entry_date=expense_date,
            description=f"Dépense : {payload.description}",
            source_type="EXPENSE",
            source_id=created.id,
            lines=[
                (ACCOUNT_EXPENSE, payload.amount, 0, payload.category),
                (ACCOUNT_CASH, 0, payload.amount, "Sortie de caisse"),
            ],
            created_by_id=created_by_id,
        )
        created.accounting_entry_id = entry.id
        await self.db.flush()
        await self.db.refresh(created)
        return created

    async def list_expenses(self, *, page: int, page_size: int, date_from: date | None, date_to: date | None):
        return await self.accounting.list_expenses_paginated(
            page=page, page_size=page_size, date_from=date_from, date_to=date_to
        )

    async def get_summary(self, *, date_from: date, date_to: date) -> AccountingSummary:
        total_revenue = await self.accounting.sum_lines_for_account_type(
            AccountType.REVENUE, side="credit", date_from=date_from, date_to=date_to
        )
        total_expense = await self.accounting.sum_lines_for_account_type(
            AccountType.EXPENSE, side="debit", date_from=date_from, date_to=date_to
        )
        cash_balance = await self.accounting.account_balance(ACCOUNT_CASH, date_from=date_from, date_to=date_to)

        return AccountingSummary(
            date_from=date_from,
            date_to=date_to,
            total_revenue=round(total_revenue, 2),
            total_expense=round(total_expense, 2),
            net_result=round(total_revenue - total_expense, 2),
            cash_balance=round(cash_balance, 2),
        )

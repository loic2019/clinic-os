"""Data access layer for Account, AccountingEntry, Expense."""

import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounting import Account, AccountingEntry, AccountingLine, AccountType, Expense


class AccountingRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # --- Accounts ---

    async def get_account_by_code(self, code: str) -> Account | None:
        result = await self.db.execute(select(Account).where(Account.code == code))
        return result.scalar_one_or_none()

    async def list_accounts(self) -> list[Account]:
        result = await self.db.execute(select(Account).where(Account.is_active.is_(True)).order_by(Account.code))
        return list(result.scalars().all())

    # --- Entries ---

    async def get_entry_by_id(self, entry_id: uuid.UUID) -> AccountingEntry | None:
        result = await self.db.execute(select(AccountingEntry).where(AccountingEntry.id == entry_id))
        return result.scalar_one_or_none()

    async def list_entries_paginated(
        self, *, page: int, page_size: int, date_from: date | None = None, date_to: date | None = None
    ) -> tuple[list[AccountingEntry], int]:
        query = select(AccountingEntry)
        count_query = select(func.count()).select_from(AccountingEntry)

        if date_from:
            query = query.where(AccountingEntry.entry_date >= date_from)
            count_query = count_query.where(AccountingEntry.entry_date >= date_from)
        if date_to:
            query = query.where(AccountingEntry.entry_date <= date_to)
            count_query = count_query.where(AccountingEntry.entry_date <= date_to)

        total = (await self.db.execute(count_query)).scalar_one()
        query = query.order_by(
            AccountingEntry.entry_date.desc(), AccountingEntry.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def create_entry(self, entry: AccountingEntry) -> AccountingEntry:
        self.db.add(entry)
        await self.db.flush()
        await self.db.refresh(entry)
        return entry

    # --- Expenses ---

    async def list_expenses_paginated(
        self, *, page: int, page_size: int, date_from: date | None = None, date_to: date | None = None
    ) -> tuple[list[Expense], int]:
        query = select(Expense)
        count_query = select(func.count()).select_from(Expense)

        if date_from:
            query = query.where(Expense.expense_date >= date_from)
            count_query = count_query.where(Expense.expense_date >= date_from)
        if date_to:
            query = query.where(Expense.expense_date <= date_to)
            count_query = count_query.where(Expense.expense_date <= date_to)

        total = (await self.db.execute(count_query)).scalar_one()
        query = query.order_by(Expense.expense_date.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def create_expense(self, expense: Expense) -> Expense:
        self.db.add(expense)
        await self.db.flush()
        await self.db.refresh(expense)
        return expense

    # --- Reporting ---

    async def sum_lines_for_account_type(
        self, account_type: AccountType, *, side: str, date_from: date, date_to: date
    ) -> float:
        """side = 'debit' or 'credit'."""
        column = AccountingLine.debit if side == "debit" else AccountingLine.credit
        result = await self.db.execute(
            select(func.coalesce(func.sum(column), 0))
            .select_from(AccountingLine)
            .join(Account, AccountingLine.account_id == Account.id)
            .join(AccountingEntry, AccountingLine.entry_id == AccountingEntry.id)
            .where(
                Account.account_type == account_type,
                AccountingEntry.entry_date >= date_from,
                AccountingEntry.entry_date <= date_to,
            )
        )
        return float(result.scalar_one())

    async def account_balance(self, code: str, *, date_from: date, date_to: date) -> float:
        account = await self.get_account_by_code(code)
        if account is None:
            return 0.0
        result = await self.db.execute(
            select(
                func.coalesce(func.sum(AccountingLine.debit), 0),
                func.coalesce(func.sum(AccountingLine.credit), 0),
            )
            .select_from(AccountingLine)
            .join(AccountingEntry, AccountingLine.entry_id == AccountingEntry.id)
            .where(
                AccountingLine.account_id == account.id,
                AccountingEntry.entry_date >= date_from,
                AccountingEntry.entry_date <= date_to,
            )
        )
        debit_sum, credit_sum = result.one()
        return float(debit_sum) - float(credit_sum)

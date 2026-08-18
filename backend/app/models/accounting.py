"""
Accounting (spec section 35): a simplified double-entry ledger.

Every significant financial operation can produce an accounting entry
(spec's example: a consultation payment -> DEBIT Caisse, CREDIT
Recettes médicales). Entries are enforced to balance (sum of debits ==
sum of credits) at the database-transaction level in the service layer
— an unbalanced entry is a bug, not a valid state.

Payments automatically generate an entry (see PaymentService); a
refund approval reverses it. Expenses are logged manually and also
produce their own balancing entry, so account balances stay accurate
without any manual bookkeeping duplication.
"""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class AccountType(str, enum.Enum):
    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    EQUITY = "EQUITY"
    REVENUE = "REVENUE"
    EXPENSE = "EXPENSE"


class Account(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "accounts"

    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    account_type: Mapped[AccountType] = mapped_column(Enum(AccountType, name="account_type"), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<Account {self.code} {self.name}>"


class AccountingEntry(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "accounting_entries"

    entry_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)

    source_type: Mapped[str] = mapped_column(
        String(32), nullable=False, doc="PAYMENT, REFUND, EXPENSE, MANUAL"
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    lines: Mapped[list["AccountingLine"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def total_debit(self) -> float:
        return round(sum(float(line.debit) for line in self.lines), 2)

    @property
    def total_credit(self) -> float:
        return round(sum(float(line.credit) for line in self.lines), 2)

    def __repr__(self) -> str:
        return f"<AccountingEntry {self.entry_number}>"


class AccountingLine(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "accounting_lines"

    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounting_entries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    debit: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    credit: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    entry: Mapped["AccountingEntry"] = relationship(back_populates="lines")
    account = relationship("Account")


class Expense(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "expenses"

    expense_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    accounting_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounting_entries.id", ondelete="SET NULL"), nullable=True
    )

    accounting_entry = relationship("AccountingEntry")

    def __repr__(self) -> str:
        return f"<Expense {self.expense_number}>"

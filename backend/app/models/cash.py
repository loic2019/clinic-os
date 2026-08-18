"""Cash registers and sessions (spec sections 19-20, 24)."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class CashSessionStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    SUSPENDED = "SUSPENDED"


class CashRegister(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "cash_registers"

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<CashRegister {self.code}>"


class CashRegisterSession(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "cash_register_sessions"

    cash_register_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cash_registers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    cashier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    opening_balance: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closing_balance: Mapped[float | None] = mapped_column(
        Numeric(12, 2), nullable=True, doc="Actual counted amount at close"
    )
    expected_balance: Mapped[float | None] = mapped_column(
        Numeric(12, 2), nullable=True, doc="opening_balance + all payments recorded during the session"
    )
    difference: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    difference_justification: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[CashSessionStatus] = mapped_column(
        Enum(CashSessionStatus, name="cash_session_status"), default=CashSessionStatus.OPEN, nullable=False
    )

    cash_register = relationship("CashRegister")
    cashier = relationship("User")

    def __repr__(self) -> str:
        return f"<CashRegisterSession {self.id} status={self.status}>"

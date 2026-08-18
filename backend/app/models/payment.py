"""Payments and refunds (spec sections 21-23, 27)."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class PaymentMethod(str, enum.Enum):
    CASH = "CASH"
    MOBILE_MONEY_MTN = "MOBILE_MONEY_MTN"
    MOBILE_MONEY_AIRTEL = "MOBILE_MONEY_AIRTEL"
    CARD = "CARD"
    BANK_TRANSFER = "BANK_TRANSFER"
    INSURANCE = "INSURANCE"
    OTHER = "OTHER"


class PaymentStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"
    VOIDED = "VOIDED"


class RefundStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class Payment(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "payments"

    payment_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    cashier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    cash_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cash_register_sessions.id", ondelete="SET NULL"), nullable=True
    )

    method: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod, name="payment_method"), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    reference: Mapped[str | None] = mapped_column(
        String(128), nullable=True, doc="External reference, e.g. mobile money transaction id"
    )
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status"), default=PaymentStatus.ACTIVE, nullable=False
    )

    invoice = relationship("Invoice", back_populates="payments")
    patient = relationship("Patient")
    cashier = relationship("User")

    refund_requests: Mapped[list["RefundRequest"]] = relationship(
        back_populates="payment", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Payment {self.payment_number}>"


class RefundRequest(UUIDPKMixin, TimestampMixin, Base):
    """Spec section 27: request -> admin validation -> refund -> accounting entry (later phase) -> audit."""

    __tablename__ = "refund_requests"

    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requested_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[RefundStatus] = mapped_column(
        Enum(RefundStatus, name="refund_status"), default=RefundStatus.PENDING, nullable=False
    )
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    payment: Mapped["Payment"] = relationship(back_populates="refund_requests")

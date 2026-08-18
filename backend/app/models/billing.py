"""
Invoicing (spec sections 15-18, 25-26).

Financial records are NEVER hard-deleted (spec section 25) — an
invoice's lifecycle moves through statuses only, and a cancellation is
a workflow (request -> admin approval) that ends in status=CANCELLED,
never a DELETE. Every invoice records who created it and, once linked
to a cash session, which session/cashier it belongs to (spec section
17), so "who created this invoice, when, from which till" is always
answerable.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class InvoiceStatus(str, enum.Enum):
    UNPAID = "UNPAID"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"
    CANCELLED = "CANCELLED"
    VOIDED = "VOIDED"


class InvoiceItemType(str, enum.Enum):
    MEDICAL_ACT = "MEDICAL_ACT"
    CONSULTATION = "CONSULTATION"
    LABORATORY = "LABORATORY"
    MEDICATION = "MEDICATION"
    IMAGING = "IMAGING"
    HOSPITALIZATION = "HOSPITALIZATION"
    SERVICE = "SERVICE"
    OTHER = "OTHER"


class CancellationStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class Invoice(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "invoices"

    invoice_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    cash_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cash_register_sessions.id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus, name="invoice_status"), default=InvoiceStatus.UNPAID, nullable=False
    )
    discount_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    patient = relationship("Patient")
    cashier = relationship("User")

    items: Mapped[list["InvoiceItem"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", lazy="selectin"
    )
    payments: Mapped[list["Payment"]] = relationship(back_populates="invoice", lazy="selectin")
    cancellation_requests: Mapped[list["CancellationRequest"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def subtotal(self) -> float:
        return round(sum(float(item.line_total) for item in self.items), 2)

    @property
    def total(self) -> float:
        return round(self.subtotal - float(self.discount_amount), 2)

    @property
    def amount_paid(self) -> float:
        from app.models.payment import PaymentStatus

        return round(
            sum(float(p.amount) for p in self.payments if p.status == PaymentStatus.ACTIVE), 2
        )

    @property
    def balance_due(self) -> float:
        return round(self.total - self.amount_paid, 2)

    def __repr__(self) -> str:
        return f"<Invoice {self.invoice_number}>"


class InvoiceItem(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "invoice_items"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_type: Mapped[InvoiceItemType] = mapped_column(Enum(InvoiceItemType, name="invoice_item_type"), nullable=False)
    medical_act_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medical_acts.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    tax_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    line_total: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    invoice: Mapped["Invoice"] = relationship(back_populates="items")
    medical_act = relationship("MedicalAct")


class CancellationRequest(UUIDPKMixin, TimestampMixin, Base):
    """Spec section 26: a cashier requests, an admin approves/rejects — never a direct delete."""

    __tablename__ = "cancellation_requests"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requested_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[CancellationStatus] = mapped_column(
        Enum(CancellationStatus, name="cancellation_status"), default=CancellationStatus.PENDING, nullable=False
    )
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    invoice: Mapped["Invoice"] = relationship(back_populates="cancellation_requests")

"""
Laboratory workflow (spec section 36):
    Prescription -> Commande -> Prélèvement -> Échantillon -> Analyse
    -> Résultat -> Validation -> Médecin -> Patient

Modeled as:
  LabTestCatalog  — catalog of orderable tests (NFS, Glycémie, ...),
                     each with a reference range for flagging abnormal
                     results.
  LabOrder        — one "commande" for a patient, optionally linked to
                     a consultation; contains one or more LabOrderItem.
  LabOrderItem     — one requested test within an order, tracks its own
                     status through the workflow.
  LabSample        — a specimen collected for an order (a single sample
                     can cover several order items, e.g. one blood draw
                     for both NFS and Glycémie).
  LabResult        — the result for one order item, entered then
                     validated by a (potentially different) lab tech.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TimestampMixin, UUIDPKMixin


class LabOrderStatus(str, enum.Enum):
    ORDERED = "ORDERED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class LabItemStatus(str, enum.Enum):
    PENDING = "PENDING"
    SAMPLE_COLLECTED = "SAMPLE_COLLECTED"
    IN_PROGRESS = "IN_PROGRESS"
    RESULT_ENTERED = "RESULT_ENTERED"
    VALIDATED = "VALIDATED"
    CANCELLED = "CANCELLED"


class SampleType(str, enum.Enum):
    BLOOD = "BLOOD"
    URINE = "URINE"
    STOOL = "STOOL"
    SWAB = "SWAB"
    OTHER = "OTHER"


class LabTestCatalog(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "laboratory_tests"

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reference_range_low: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
    reference_range_high: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
    reference_range_text: Mapped[str | None] = mapped_column(
        String(255), nullable=True, doc="For non-numeric results, e.g. 'Négatif'"
    )
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<LabTestCatalog {self.code} {self.name}>"


class LabOrder(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "laboratory_orders"

    order_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    doctor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("doctors.id", ondelete="SET NULL"), nullable=True
    )
    consultation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consultations.id", ondelete="SET NULL"), nullable=True
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[LabOrderStatus] = mapped_column(
        Enum(LabOrderStatus, name="lab_order_status"), default=LabOrderStatus.ORDERED, nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    patient = relationship("Patient")
    doctor = relationship("Doctor")

    items: Mapped[list["LabOrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )
    samples: Mapped[list["LabSample"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<LabOrder {self.order_number}>"


class LabOrderItem(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "laboratory_order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("laboratory_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lab_test_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("laboratory_tests.id", ondelete="RESTRICT"), nullable=False
    )
    test_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[LabItemStatus] = mapped_column(
        Enum(LabItemStatus, name="lab_item_status"), default=LabItemStatus.PENDING, nullable=False
    )

    order: Mapped["LabOrder"] = relationship(back_populates="items")
    lab_test = relationship("LabTestCatalog")
    result: Mapped["LabResult | None"] = relationship(
        back_populates="order_item", cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )


class LabSample(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "laboratory_samples"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("laboratory_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sample_type: Mapped[SampleType] = mapped_column(Enum(SampleType, name="lab_sample_type"), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    collected_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    order: Mapped["LabOrder"] = relationship(back_populates="samples")


class LabResult(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "laboratory_results"

    order_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("laboratory_order_items.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    value_numeric: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
    value_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reference_range_display: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_abnormal: Mapped[bool] = mapped_column(default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    entered_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    entered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    validated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    order_item: Mapped["LabOrderItem"] = relationship(back_populates="result")

"""
Consultations (spec section 12): vitals, clinical exam, diagnosis,
linked medical acts (each with its OWN price snapshot — spec section
14's rule that an invoice must keep the price actually applied),
recommendations, and prescriptions.
"""

import uuid
from datetime import date

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class Consultation(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "consultations"

    consultation_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    doctor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("doctors.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # --- Vitals (spec section 12) ---
    symptoms: Mapped[str | None] = mapped_column(Text, nullable=True)
    temperature_celsius: Mapped[float | None] = mapped_column(Numeric(4, 1), nullable=True)
    blood_pressure_systolic: Mapped[int | None] = mapped_column(Integer, nullable=True)
    blood_pressure_diastolic: Mapped[int | None] = mapped_column(Integer, nullable=True)
    heart_rate_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    height_cm: Mapped[float | None] = mapped_column(Numeric(5, 1), nullable=True)
    oxygen_saturation: Mapped[float | None] = mapped_column(Numeric(4, 1), nullable=True)

    clinical_exam: Mapped[str | None] = mapped_column(Text, nullable=True)
    diagnosis: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendations: Mapped[str | None] = mapped_column(Text, nullable=True)

    patient = relationship("Patient")
    doctor = relationship("Doctor")

    acts: Mapped[list["ConsultationAct"]] = relationship(
        back_populates="consultation", cascade="all, delete-orphan", lazy="selectin"
    )
    prescriptions: Mapped[list["Prescription"]] = relationship(
        back_populates="consultation", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def bmi(self) -> float | None:
        if not self.weight_kg or not self.height_cm:
            return None
        height_m = float(self.height_cm) / 100
        if height_m <= 0:
            return None
        return round(float(self.weight_kg) / (height_m**2), 1)

    def __repr__(self) -> str:
        return f"<Consultation {self.consultation_number}>"


class ConsultationAct(UUIDPKMixin, TimestampMixin, Base):
    """A medical act performed during a consultation, with its own
    price snapshot so later catalog price changes never retroactively
    alter what was actually charged (spec section 14)."""

    __tablename__ = "consultation_acts"

    consultation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consultations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    medical_act_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medical_acts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_price_applied: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    act_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)

    consultation: Mapped["Consultation"] = relationship(back_populates="acts")
    medical_act = relationship("MedicalAct")


class Prescription(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "prescriptions"

    consultation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consultations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    doctor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("doctors.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    consultation: Mapped["Consultation"] = relationship(back_populates="prescriptions")
    items: Mapped[list["PrescriptionItem"]] = relationship(
        back_populates="prescription", cascade="all, delete-orphan", lazy="selectin"
    )


class PrescriptionItem(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "prescription_items"

    prescription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prescriptions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    medication_name: Mapped[str] = mapped_column(String(255), nullable=False)
    dosage: Mapped[str | None] = mapped_column(String(128), nullable=True)
    frequency: Mapped[str | None] = mapped_column(String(128), nullable=True)
    duration: Mapped[str | None] = mapped_column(String(128), nullable=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)

    prescription: Mapped["Prescription"] = relationship(back_populates="items")

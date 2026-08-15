"""
Patient records (spec sections 10-11).

Patient is soft-deleted only (archived — spec section 10's "archiver"),
never hard-deleted. Contacts, insurances, allergies, and medical history
entries are child records managed through their own endpoints so the
UI can add/edit/remove them independently without re-submitting the
whole patient record each time.
"""

import enum
import uuid
from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TimestampMixin, UUIDPKMixin


class Gender(str, enum.Enum):
    MALE = "M"
    FEMALE = "F"
    OTHER = "OTHER"


class BloodGroup(str, enum.Enum):
    O_POS = "O+"
    O_NEG = "O-"
    A_POS = "A+"
    A_NEG = "A-"
    B_POS = "B+"
    B_NEG = "B-"
    AB_POS = "AB+"
    AB_NEG = "AB-"
    UNKNOWN = "UNKNOWN"


class Patient(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "patients"

    patient_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)

    first_name: Mapped[str] = mapped_column(String(128), nullable=False)
    last_name: Mapped[str] = mapped_column(String(128), nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[Gender | None] = mapped_column(Enum(Gender, name="patient_gender"), nullable=True)

    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)

    blood_group: Mapped[BloodGroup | None] = mapped_column(
        Enum(BloodGroup, name="patient_blood_group"), nullable=True
    )
    observations: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    contacts: Mapped[list["PatientContact"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan", lazy="selectin"
    )
    insurances: Mapped[list["PatientInsurance"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan", lazy="selectin"
    )
    allergies: Mapped[list["PatientAllergy"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan", lazy="selectin"
    )
    medical_histories: Mapped[list["MedicalHistory"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        return f"<Patient {self.patient_number} {self.full_name}>"


class PatientContact(UUIDPKMixin, TimestampMixin, Base):
    """Personne à contacter (spec section 10)."""

    __tablename__ = "patient_contacts"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    relationship_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="contacts")


class PatientInsurance(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "patient_insurances"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    insurance_name: Mapped[str] = mapped_column(String(255), nullable=False)
    insurance_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_primary: Mapped[bool] = mapped_column(default=False, nullable=False)

    patient: Mapped["Patient"] = relationship(back_populates="insurances")


class PatientAllergy(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "patient_allergies"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    allergen: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[str | None] = mapped_column(String(32), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="allergies")


class MedicalHistory(UUIDPKMixin, TimestampMixin, Base):
    """Antécédents médicaux (spec section 10)."""

    __tablename__ = "medical_histories"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    condition: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_on: Mapped[date | None] = mapped_column(Date, nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="medical_histories")

"""
Doctor records (spec section 39 references "Médecin" throughout the
medical workflow; the dedicated `doctors` table is listed in spec
section 53). A doctor may optionally be linked to a login account
(user_id) — some clinics keep doctor records for scheduling/attribution
purposes without necessarily granting every doctor a system login.
"""

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TimestampMixin, UUIDPKMixin


class Doctor(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "doctors"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, unique=True
    )

    first_name: Mapped[str] = mapped_column(String(128), nullable=False)
    last_name: Mapped[str] = mapped_column(String(128), nullable=False)
    specialty: Mapped[str | None] = mapped_column(String(128), nullable=True)
    license_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    user = relationship("User")

    @property
    def full_name(self) -> str:
        return f"Dr. {self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        return f"<Doctor {self.full_name}>"

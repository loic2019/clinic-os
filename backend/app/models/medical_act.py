"""
Medical act catalog (spec section 13) and its price history (spec
section 14).

Prices are NEVER overwritten — each price change is a new
MedicalActPrice row with an effective_from date. The "current price" is
whichever row has the latest effective_from that is not in the future.
An already-issued invoice line stores its own snapshot of the price
that applied at the time (see ConsultationAct.unit_price_applied in
consultation.py), so raising a price later never changes a historical
invoice.
"""

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TimestampMixin, UUIDPKMixin


class MedicalAct(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "medical_acts"

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    tax_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    service: Mapped[str | None] = mapped_column(String(128), nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    prices: Mapped[list["MedicalActPrice"]] = relationship(
        back_populates="medical_act",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="MedicalActPrice.effective_from.desc()",
    )

    @property
    def current_price(self) -> "MedicalActPrice | None":
        today = date.today()
        applicable = [p for p in self.prices if p.effective_from <= today]
        if not applicable:
            return None
        # Ties on effective_from (e.g. two price changes the same day) are
        # broken by created_at, so the most recently entered price always
        # wins — deterministic regardless of relationship load order.
        return max(applicable, key=lambda p: (p.effective_from, p.created_at))

    def __repr__(self) -> str:
        return f"<MedicalAct {self.code} {self.name}>"


class MedicalActPrice(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "medical_act_prices"

    medical_act_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medical_acts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)

    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    medical_act: Mapped["MedicalAct"] = relationship(back_populates="prices")

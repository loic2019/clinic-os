"""
Backing table for auto-generated document numbers (spec section 56):
    PAT-2026-000001, CONS-2026-000001, FAC-2026-000001, ...

One row per (key, year), incremented atomically via a single upsert
statement (see app.services.numbering_service) so concurrent requests
from multiple users never produce duplicate numbers, without needing
explicit application-level locking.
"""

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import UUIDPKMixin


class NumberingSequence(UUIDPKMixin, Base):
    __tablename__ = "numbering_sequences"
    __table_args__ = (UniqueConstraint("key", "year", name="uq_numbering_key_year"),)

    key: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

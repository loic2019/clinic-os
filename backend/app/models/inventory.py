"""
Inventory (spec section 45): medications, consumables, lab supplies,
medical equipment, office supplies, cleaning products — one unified
catalog, each item optionally tracked in batches (for perishables, so
expiry alerts and FEFO dispensing are possible later in the Pharmacy
module).

`InventoryItem.quantity_on_hand` is a maintained running total, updated
transactionally by InventoryService whenever a movement is recorded —
reads (stock levels, low-stock alerts) never need to sum movement
history, which matters once that history is large.
"""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TimestampMixin, UUIDPKMixin


class InventoryCategory(str, enum.Enum):
    MEDICATION = "MEDICATION"
    CONSUMABLE = "CONSUMABLE"
    LAB_SUPPLY = "LAB_SUPPLY"
    MEDICAL_EQUIPMENT = "MEDICAL_EQUIPMENT"
    OFFICE_SUPPLY = "OFFICE_SUPPLY"
    CLEANING = "CLEANING"


class MovementType(str, enum.Enum):
    PURCHASE = "PURCHASE"
    SALE = "SALE"
    DISPENSATION = "DISPENSATION"
    TRANSFER = "TRANSFER"
    ADJUSTMENT = "ADJUSTMENT"
    RETURN = "RETURN"
    EXPIRATION = "EXPIRATION"


# Movement types that ADD to stock vs. REMOVE from stock — used to sign
# the quantity delta consistently everywhere instead of trusting the
# caller to pass a correctly-signed number.
INBOUND_MOVEMENT_TYPES = {MovementType.PURCHASE, MovementType.RETURN}
OUTBOUND_MOVEMENT_TYPES = {MovementType.SALE, MovementType.DISPENSATION, MovementType.EXPIRATION}
# TRANSFER and ADJUSTMENT can go either way — sign is taken from the
# caller-supplied quantity directly (positive = in, negative = out).


class InventoryItem(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "inventory_items"

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[InventoryCategory] = mapped_column(
        Enum(InventoryCategory, name="inventory_category"), nullable=False, index=True
    )
    unit: Mapped[str] = mapped_column(String(32), nullable=False, doc="e.g. box, piece, bottle")
    quantity_on_hand: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reorder_threshold: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_perishable: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    batches: Mapped[list["InventoryBatch"]] = relationship(
        back_populates="inventory_item", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def is_low_stock(self) -> bool:
        return self.quantity_on_hand <= self.reorder_threshold

    def __repr__(self) -> str:
        return f"<InventoryItem {self.code} {self.name}>"


class InventoryBatch(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "inventory_batches"

    inventory_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    batch_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True
    )
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    inventory_item: Mapped["InventoryItem"] = relationship(back_populates="batches")

    def __repr__(self) -> str:
        return f"<InventoryBatch {self.batch_number} qty={self.quantity}>"


class InventoryMovement(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "inventory_movements"

    inventory_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory_batches.id", ondelete="SET NULL"), nullable=True
    )
    movement_type: Mapped[MovementType] = mapped_column(Enum(MovementType, name="movement_type"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, doc="Signed: positive=in, negative=out")
    reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    inventory_item = relationship("InventoryItem")
    batch = relationship("InventoryBatch")

    def __repr__(self) -> str:
        return f"<InventoryMovement {self.movement_type} {self.quantity}>"

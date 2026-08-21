"""Pydantic schemas for /api/inventory."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.inventory import InventoryCategory, MovementType


class InventoryItemCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1, max_length=255)
    category: InventoryCategory
    unit: str = Field(..., min_length=1, max_length=32, examples=["boîte", "unité", "flacon"])
    reorder_threshold: int = Field(default=0, ge=0)
    is_perishable: bool = False


class InventoryItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    category: InventoryCategory | None = None
    unit: str | None = None
    reorder_threshold: int | None = Field(default=None, ge=0)
    is_perishable: bool | None = None
    is_active: bool | None = None


class InventoryItemRead(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    category: InventoryCategory
    unit: str
    quantity_on_hand: int
    reorder_threshold: int
    is_perishable: bool
    is_active: bool
    is_low_stock: bool

    model_config = {"from_attributes": True}


class InventoryItemListResponse(BaseModel):
    items: list[InventoryItemRead]
    total: int
    page: int
    page_size: int


class InventoryBatchRead(BaseModel):
    id: uuid.UUID
    batch_number: str | None
    quantity: int
    expiry_date: date | None
    received_at: datetime

    model_config = {"from_attributes": True}


class MovementCreate(BaseModel):
    movement_type: MovementType
    quantity: int = Field(..., description="Positive number; direction is derived from movement_type.")
    batch_id: uuid.UUID | None = None
    reference: str | None = None
    notes: str | None = None


class MovementRead(BaseModel):
    id: uuid.UUID
    inventory_item_id: uuid.UUID
    batch_id: uuid.UUID | None
    movement_type: MovementType
    quantity: int
    reference: str | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MovementListResponse(BaseModel):
    items: list[MovementRead]
    total: int
    page: int
    page_size: int


class LowStockAlert(BaseModel):
    inventory_item_id: uuid.UUID
    code: str
    name: str
    quantity_on_hand: int
    reorder_threshold: int


class ExpiryAlert(BaseModel):
    inventory_item_id: uuid.UUID
    item_code: str
    item_name: str
    batch_id: uuid.UUID
    batch_number: str | None
    quantity: int
    expiry_date: date
    days_until_expiry: int


class InventoryAlerts(BaseModel):
    low_stock: list[LowStockAlert]
    expiring_soon: list[ExpiryAlert]
    expired: list[ExpiryAlert]

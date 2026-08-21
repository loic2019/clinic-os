"""Pydantic schemas for /api/suppliers and /api/purchase-orders."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.supplier import PurchaseOrderStatus


class SupplierCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1, max_length=255)
    contact_name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    address: str | None = None


class SupplierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    contact_name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    address: str | None = None
    is_active: bool | None = None


class SupplierRead(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    contact_name: str | None
    phone: str | None
    email: str | None
    address: str | None
    is_active: bool

    model_config = {"from_attributes": True}


class SupplierListResponse(BaseModel):
    items: list[SupplierRead]
    total: int
    page: int
    page_size: int


class PurchaseOrderItemInput(BaseModel):
    inventory_item_id: uuid.UUID
    quantity_ordered: int = Field(..., gt=0)
    unit_price: float = Field(..., gt=0)


class PurchaseOrderItemRead(BaseModel):
    id: uuid.UUID
    inventory_item_id: uuid.UUID
    quantity_ordered: int
    quantity_received: int
    unit_price: float

    model_config = {"from_attributes": True}


class PurchaseOrderCreate(BaseModel):
    supplier_id: uuid.UUID
    notes: str | None = None
    items: list[PurchaseOrderItemInput] = Field(..., min_length=1)


class ReceiveItemInput(BaseModel):
    purchase_order_item_id: uuid.UUID
    quantity_received: int = Field(..., gt=0)
    batch_number: str | None = None
    expiry_date: date | None = Field(default=None, description="Required for perishable items.")


class ReceiveOrderInput(BaseModel):
    items: list[ReceiveItemInput] = Field(..., min_length=1)


class PurchaseOrderListItem(BaseModel):
    id: uuid.UUID
    order_number: str
    supplier_id: uuid.UUID
    status: PurchaseOrderStatus
    total_amount: float
    created_at: datetime

    model_config = {"from_attributes": True}


class PurchaseOrderRead(PurchaseOrderListItem):
    notes: str | None
    items: list[PurchaseOrderItemRead]


class PurchaseOrderListResponse(BaseModel):
    items: list[PurchaseOrderListItem]
    total: int
    page: int
    page_size: int

"""Data access layer for Supplier, PurchaseOrder, PurchaseOrderItem."""

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.supplier import PurchaseOrder, PurchaseOrderItem, Supplier


class SupplierRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, supplier_id: uuid.UUID) -> Supplier | None:
        result = await self.db.execute(
            select(Supplier).where(Supplier.id == supplier_id, Supplier.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> Supplier | None:
        result = await self.db.execute(select(Supplier).where(Supplier.code == code))
        return result.scalar_one_or_none()

    async def list_paginated(
        self, *, page: int, page_size: int, search: str | None = None, active_only: bool = True
    ) -> tuple[list[Supplier], int]:
        query = select(Supplier).where(Supplier.deleted_at.is_(None))
        count_query = select(func.count()).select_from(Supplier).where(Supplier.deleted_at.is_(None))

        if active_only:
            query = query.where(Supplier.is_active.is_(True))
            count_query = count_query.where(Supplier.is_active.is_(True))
        if search:
            pattern = f"%{search}%"
            condition = or_(Supplier.code.ilike(pattern), Supplier.name.ilike(pattern))
            query = query.where(condition)
            count_query = count_query.where(condition)

        total = (await self.db.execute(count_query)).scalar_one()
        query = query.order_by(Supplier.name.asc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def create(self, supplier: Supplier) -> Supplier:
        self.db.add(supplier)
        await self.db.flush()
        await self.db.refresh(supplier)
        return supplier

    async def save(self, supplier: Supplier) -> Supplier:
        await self.db.flush()
        await self.db.refresh(supplier)
        return supplier


class PurchaseOrderRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, order_id: uuid.UUID) -> PurchaseOrder | None:
        result = await self.db.execute(select(PurchaseOrder).where(PurchaseOrder.id == order_id))
        return result.scalar_one_or_none()

    async def get_item(self, order_id: uuid.UUID, item_id: uuid.UUID) -> PurchaseOrderItem | None:
        result = await self.db.execute(
            select(PurchaseOrderItem).where(
                PurchaseOrderItem.id == item_id, PurchaseOrderItem.purchase_order_id == order_id
            )
        )
        return result.scalar_one_or_none()

    async def list_paginated(
        self, *, page: int, page_size: int, supplier_id: uuid.UUID | None = None, status: str | None = None
    ) -> tuple[list[PurchaseOrder], int]:
        query = select(PurchaseOrder)
        count_query = select(func.count()).select_from(PurchaseOrder)

        if supplier_id:
            query = query.where(PurchaseOrder.supplier_id == supplier_id)
            count_query = count_query.where(PurchaseOrder.supplier_id == supplier_id)
        if status:
            query = query.where(PurchaseOrder.status == status)
            count_query = count_query.where(PurchaseOrder.status == status)

        total = (await self.db.execute(count_query)).scalar_one()
        query = query.order_by(PurchaseOrder.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def create(self, order: PurchaseOrder) -> PurchaseOrder:
        self.db.add(order)
        await self.db.flush()
        await self.db.refresh(order)
        return order

    async def save(self, order: PurchaseOrder) -> PurchaseOrder:
        await self.db.flush()
        await self.db.refresh(order)
        return order

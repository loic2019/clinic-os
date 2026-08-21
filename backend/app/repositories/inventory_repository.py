"""Data access layer for InventoryItem, InventoryBatch, InventoryMovement."""

import uuid
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import InventoryBatch, InventoryItem, InventoryMovement


class InventoryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # --- Items ---

    async def get_item_by_id(self, item_id: uuid.UUID) -> InventoryItem | None:
        result = await self.db.execute(
            select(InventoryItem).where(InventoryItem.id == item_id, InventoryItem.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_item_by_code(self, code: str) -> InventoryItem | None:
        result = await self.db.execute(select(InventoryItem).where(InventoryItem.code == code))
        return result.scalar_one_or_none()

    async def list_items_paginated(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None = None,
        category: str | None = None,
        active_only: bool = True,
    ) -> tuple[list[InventoryItem], int]:
        query = select(InventoryItem).where(InventoryItem.deleted_at.is_(None))
        count_query = select(func.count()).select_from(InventoryItem).where(InventoryItem.deleted_at.is_(None))

        if active_only:
            query = query.where(InventoryItem.is_active.is_(True))
            count_query = count_query.where(InventoryItem.is_active.is_(True))
        if category:
            query = query.where(InventoryItem.category == category)
            count_query = count_query.where(InventoryItem.category == category)
        if search:
            pattern = f"%{search}%"
            condition = or_(InventoryItem.code.ilike(pattern), InventoryItem.name.ilike(pattern))
            query = query.where(condition)
            count_query = count_query.where(condition)

        total = (await self.db.execute(count_query)).scalar_one()
        query = query.order_by(InventoryItem.name.asc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def list_all_active_items(self) -> list[InventoryItem]:
        result = await self.db.execute(
            select(InventoryItem).where(InventoryItem.deleted_at.is_(None), InventoryItem.is_active.is_(True))
        )
        return list(result.scalars().all())

    async def create_item(self, item: InventoryItem) -> InventoryItem:
        self.db.add(item)
        await self.db.flush()
        await self.db.refresh(item)
        return item

    async def save_item(self, item: InventoryItem) -> InventoryItem:
        await self.db.flush()
        await self.db.refresh(item)
        return item

    # --- Batches ---

    async def get_batch_by_id(self, batch_id: uuid.UUID) -> InventoryBatch | None:
        result = await self.db.execute(select(InventoryBatch).where(InventoryBatch.id == batch_id))
        return result.scalar_one_or_none()

    async def create_batch(self, batch: InventoryBatch) -> InventoryBatch:
        self.db.add(batch)
        await self.db.flush()
        await self.db.refresh(batch)
        return batch

    async def save_batch(self, batch: InventoryBatch) -> InventoryBatch:
        await self.db.flush()
        await self.db.refresh(batch)
        return batch

    async def list_batches_expiring_between(self, date_from: date, date_to: date) -> list[InventoryBatch]:
        result = await self.db.execute(
            select(InventoryBatch).where(
                InventoryBatch.expiry_date.is_not(None),
                InventoryBatch.expiry_date >= date_from,
                InventoryBatch.expiry_date <= date_to,
                InventoryBatch.quantity > 0,
            )
        )
        return list(result.scalars().all())

    async def list_expired_batches(self, as_of: date) -> list[InventoryBatch]:
        result = await self.db.execute(
            select(InventoryBatch).where(
                InventoryBatch.expiry_date.is_not(None),
                InventoryBatch.expiry_date < as_of,
                InventoryBatch.quantity > 0,
            )
        )
        return list(result.scalars().all())

    # --- Movements ---

    async def create_movement(self, movement: InventoryMovement) -> InventoryMovement:
        self.db.add(movement)
        await self.db.flush()
        await self.db.refresh(movement)
        return movement

    async def list_movements_paginated(
        self, *, page: int, page_size: int, inventory_item_id: uuid.UUID | None = None
    ) -> tuple[list[InventoryMovement], int]:
        query = select(InventoryMovement)
        count_query = select(func.count()).select_from(InventoryMovement)

        if inventory_item_id:
            query = query.where(InventoryMovement.inventory_item_id == inventory_item_id)
            count_query = count_query.where(InventoryMovement.inventory_item_id == inventory_item_id)

        total = (await self.db.execute(count_query)).scalar_one()
        query = query.order_by(InventoryMovement.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

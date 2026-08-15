"""Data access layer for the laboratory module."""

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.laboratory import LabOrder, LabOrderItem, LabTestCatalog


class LabTestRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, test_id: uuid.UUID) -> LabTestCatalog | None:
        result = await self.db.execute(
            select(LabTestCatalog).where(LabTestCatalog.id == test_id, LabTestCatalog.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> LabTestCatalog | None:
        result = await self.db.execute(select(LabTestCatalog).where(LabTestCatalog.code == code))
        return result.scalar_one_or_none()

    async def list_paginated(
        self, *, page: int, page_size: int, search: str | None = None, active_only: bool = True
    ) -> tuple[list[LabTestCatalog], int]:
        query = select(LabTestCatalog).where(LabTestCatalog.deleted_at.is_(None))
        count_query = select(func.count()).select_from(LabTestCatalog).where(LabTestCatalog.deleted_at.is_(None))

        if active_only:
            query = query.where(LabTestCatalog.is_active.is_(True))
            count_query = count_query.where(LabTestCatalog.is_active.is_(True))

        if search:
            pattern = f"%{search}%"
            condition = or_(LabTestCatalog.code.ilike(pattern), LabTestCatalog.name.ilike(pattern))
            query = query.where(condition)
            count_query = count_query.where(condition)

        total = (await self.db.execute(count_query)).scalar_one()
        query = query.order_by(LabTestCatalog.category.asc(), LabTestCatalog.name.asc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def create(self, test: LabTestCatalog) -> LabTestCatalog:
        self.db.add(test)
        await self.db.flush()
        await self.db.refresh(test)
        return test

    async def save(self, test: LabTestCatalog) -> LabTestCatalog:
        await self.db.flush()
        await self.db.refresh(test)
        return test


class LabOrderRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, order_id: uuid.UUID) -> LabOrder | None:
        result = await self.db.execute(select(LabOrder).where(LabOrder.id == order_id))
        return result.scalar_one_or_none()

    async def get_item(self, order_id: uuid.UUID, item_id: uuid.UUID) -> LabOrderItem | None:
        result = await self.db.execute(
            select(LabOrderItem).where(LabOrderItem.id == item_id, LabOrderItem.order_id == order_id)
        )
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        *,
        page: int,
        page_size: int,
        patient_id: uuid.UUID | None = None,
        status: str | None = None,
    ) -> tuple[list[LabOrder], int]:
        query = select(LabOrder)
        count_query = select(func.count()).select_from(LabOrder)

        if patient_id:
            query = query.where(LabOrder.patient_id == patient_id)
            count_query = count_query.where(LabOrder.patient_id == patient_id)
        if status:
            query = query.where(LabOrder.status == status)
            count_query = count_query.where(LabOrder.status == status)

        total = (await self.db.execute(count_query)).scalar_one()
        query = query.order_by(LabOrder.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def create(self, order: LabOrder) -> LabOrder:
        self.db.add(order)
        await self.db.flush()
        await self.db.refresh(order)
        return order

    async def save(self, order: LabOrder) -> LabOrder:
        await self.db.flush()
        await self.db.refresh(order)
        return order

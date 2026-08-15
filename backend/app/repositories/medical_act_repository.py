"""Data access layer for MedicalAct and its price history."""

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.medical_act import MedicalAct, MedicalActPrice


class MedicalActRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, medical_act_id: uuid.UUID) -> MedicalAct | None:
        result = await self.db.execute(
            select(MedicalAct).where(MedicalAct.id == medical_act_id, MedicalAct.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> MedicalAct | None:
        result = await self.db.execute(select(MedicalAct).where(MedicalAct.code == code))
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None = None,
        category: str | None = None,
        active_only: bool = True,
    ) -> tuple[list[MedicalAct], int]:
        query = select(MedicalAct).where(MedicalAct.deleted_at.is_(None))
        count_query = select(func.count()).select_from(MedicalAct).where(MedicalAct.deleted_at.is_(None))

        if active_only:
            query = query.where(MedicalAct.is_active.is_(True))
            count_query = count_query.where(MedicalAct.is_active.is_(True))

        if category:
            query = query.where(MedicalAct.category == category)
            count_query = count_query.where(MedicalAct.category == category)

        if search:
            pattern = f"%{search}%"
            condition = or_(MedicalAct.code.ilike(pattern), MedicalAct.name.ilike(pattern))
            query = query.where(condition)
            count_query = count_query.where(condition)

        total = (await self.db.execute(count_query)).scalar_one()
        query = query.order_by(MedicalAct.category.asc(), MedicalAct.name.asc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def create(self, medical_act: MedicalAct) -> MedicalAct:
        self.db.add(medical_act)
        await self.db.flush()
        await self.db.refresh(medical_act)
        return medical_act

    async def save(self, medical_act: MedicalAct) -> MedicalAct:
        await self.db.flush()
        await self.db.refresh(medical_act)
        return medical_act

    async def add_price(self, price: MedicalActPrice) -> MedicalActPrice:
        self.db.add(price)
        await self.db.flush()
        await self.db.refresh(price)
        return price

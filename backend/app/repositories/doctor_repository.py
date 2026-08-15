"""Data access layer for Doctor."""

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.doctor import Doctor


class DoctorRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, doctor_id: uuid.UUID) -> Doctor | None:
        result = await self.db.execute(
            select(Doctor).where(Doctor.id == doctor_id, Doctor.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def list_paginated(
        self, *, page: int, page_size: int, search: str | None = None, active_only: bool = True
    ) -> tuple[list[Doctor], int]:
        query = select(Doctor).where(Doctor.deleted_at.is_(None))
        count_query = select(func.count()).select_from(Doctor).where(Doctor.deleted_at.is_(None))

        if active_only:
            query = query.where(Doctor.is_active.is_(True))
            count_query = count_query.where(Doctor.is_active.is_(True))

        if search:
            pattern = f"%{search}%"
            condition = or_(
                Doctor.first_name.ilike(pattern),
                Doctor.last_name.ilike(pattern),
                Doctor.specialty.ilike(pattern),
            )
            query = query.where(condition)
            count_query = count_query.where(condition)

        total = (await self.db.execute(count_query)).scalar_one()
        query = query.order_by(Doctor.last_name.asc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def create(self, doctor: Doctor) -> Doctor:
        self.db.add(doctor)
        await self.db.flush()
        await self.db.refresh(doctor)
        return doctor

    async def save(self, doctor: Doctor) -> Doctor:
        await self.db.flush()
        await self.db.refresh(doctor)
        return doctor

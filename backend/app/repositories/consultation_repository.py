"""Data access layer for Consultation."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.consultation import Consultation


class ConsultationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, consultation_id: uuid.UUID) -> Consultation | None:
        result = await self.db.execute(
            select(Consultation).where(Consultation.id == consultation_id)
        )
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        *,
        page: int,
        page_size: int,
        patient_id: uuid.UUID | None = None,
        doctor_id: uuid.UUID | None = None,
    ) -> tuple[list[Consultation], int]:
        query = select(Consultation)
        count_query = select(func.count()).select_from(Consultation)

        if patient_id:
            query = query.where(Consultation.patient_id == patient_id)
            count_query = count_query.where(Consultation.patient_id == patient_id)
        if doctor_id:
            query = query.where(Consultation.doctor_id == doctor_id)
            count_query = count_query.where(Consultation.doctor_id == doctor_id)

        total = (await self.db.execute(count_query)).scalar_one()
        query = query.order_by(Consultation.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def create(self, consultation: Consultation) -> Consultation:
        self.db.add(consultation)
        await self.db.flush()
        await self.db.refresh(consultation)
        return consultation

    async def save(self, consultation: Consultation) -> Consultation:
        await self.db.flush()
        await self.db.refresh(consultation)
        return consultation

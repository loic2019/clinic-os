"""Data access layer for Invoice, InvoiceItem, CancellationRequest."""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import CancellationRequest, Invoice


class InvoiceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, invoice_id: uuid.UUID) -> Invoice | None:
        result = await self.db.execute(select(Invoice).where(Invoice.id == invoice_id))
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        *,
        page: int,
        page_size: int,
        cashier_id: uuid.UUID | None = None,
        patient_id: uuid.UUID | None = None,
        status: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[Invoice], int]:
        query = select(Invoice)
        count_query = select(func.count()).select_from(Invoice)

        if cashier_id:
            query = query.where(Invoice.created_by_id == cashier_id)
            count_query = count_query.where(Invoice.created_by_id == cashier_id)
        if patient_id:
            query = query.where(Invoice.patient_id == patient_id)
            count_query = count_query.where(Invoice.patient_id == patient_id)
        if status:
            query = query.where(Invoice.status == status)
            count_query = count_query.where(Invoice.status == status)
        if date_from:
            query = query.where(Invoice.created_at >= date_from)
            count_query = count_query.where(Invoice.created_at >= date_from)
        if date_to:
            query = query.where(Invoice.created_at <= date_to)
            count_query = count_query.where(Invoice.created_at <= date_to)

        total = (await self.db.execute(count_query)).scalar_one()
        query = query.order_by(Invoice.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def create(self, invoice: Invoice) -> Invoice:
        self.db.add(invoice)
        await self.db.flush()
        await self.db.refresh(invoice)
        return invoice

    async def save(self, invoice: Invoice) -> Invoice:
        await self.db.flush()
        await self.db.refresh(invoice)
        return invoice

    async def get_cancellation_request(self, request_id: uuid.UUID) -> CancellationRequest | None:
        result = await self.db.execute(
            select(CancellationRequest).where(CancellationRequest.id == request_id)
        )
        return result.scalar_one_or_none()

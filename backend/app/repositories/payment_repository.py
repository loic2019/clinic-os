"""Data access layer for Payment, RefundRequest."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment, RefundRequest


class PaymentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, payment_id: uuid.UUID) -> Payment | None:
        result = await self.db.execute(select(Payment).where(Payment.id == payment_id))
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        *,
        page: int,
        page_size: int,
        invoice_id: uuid.UUID | None = None,
        cashier_id: uuid.UUID | None = None,
        cash_session_id: uuid.UUID | None = None,
    ) -> tuple[list[Payment], int]:
        query = select(Payment)
        count_query = select(func.count()).select_from(Payment)

        if invoice_id:
            query = query.where(Payment.invoice_id == invoice_id)
            count_query = count_query.where(Payment.invoice_id == invoice_id)
        if cashier_id:
            query = query.where(Payment.cashier_id == cashier_id)
            count_query = count_query.where(Payment.cashier_id == cashier_id)
        if cash_session_id:
            query = query.where(Payment.cash_session_id == cash_session_id)
            count_query = count_query.where(Payment.cash_session_id == cash_session_id)

        total = (await self.db.execute(count_query)).scalar_one()
        query = query.order_by(Payment.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def sum_active_amount_for_session(self, cash_session_id: uuid.UUID) -> float:
        from app.models.payment import PaymentStatus

        result = await self.db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.cash_session_id == cash_session_id, Payment.status == PaymentStatus.ACTIVE
            )
        )
        return float(result.scalar_one())

    async def create(self, payment: Payment) -> Payment:
        self.db.add(payment)
        await self.db.flush()
        await self.db.refresh(payment)
        return payment

    async def save(self, payment: Payment) -> Payment:
        await self.db.flush()
        await self.db.refresh(payment)
        return payment

    async def get_refund_request(self, request_id: uuid.UUID) -> RefundRequest | None:
        result = await self.db.execute(select(RefundRequest).where(RefundRequest.id == request_id))
        return result.scalar_one_or_none()

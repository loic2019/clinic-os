"""Data access layer for CashRegister, CashRegisterSession."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cash import CashRegister, CashRegisterSession, CashSessionStatus


class CashRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_register_by_id(self, register_id: uuid.UUID) -> CashRegister | None:
        result = await self.db.execute(select(CashRegister).where(CashRegister.id == register_id))
        return result.scalar_one_or_none()

    async def list_registers(self) -> list[CashRegister]:
        result = await self.db.execute(select(CashRegister).where(CashRegister.is_active.is_(True)))
        return list(result.scalars().all())

    async def get_session_by_id(self, session_id: uuid.UUID) -> CashRegisterSession | None:
        result = await self.db.execute(
            select(CashRegisterSession).where(CashRegisterSession.id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_open_session_for_user(self, cashier_id: uuid.UUID) -> CashRegisterSession | None:
        result = await self.db.execute(
            select(CashRegisterSession).where(
                CashRegisterSession.cashier_id == cashier_id,
                CashRegisterSession.status == CashSessionStatus.OPEN,
            )
        )
        return result.scalar_one_or_none()

    async def get_open_session_for_register(self, register_id: uuid.UUID) -> CashRegisterSession | None:
        result = await self.db.execute(
            select(CashRegisterSession).where(
                CashRegisterSession.cash_register_id == register_id,
                CashRegisterSession.status == CashSessionStatus.OPEN,
            )
        )
        return result.scalar_one_or_none()

    async def list_paginated(
        self, *, page: int, page_size: int, cashier_id: uuid.UUID | None = None
    ) -> tuple[list[CashRegisterSession], int]:
        query = select(CashRegisterSession)
        count_query = select(func.count()).select_from(CashRegisterSession)

        if cashier_id:
            query = query.where(CashRegisterSession.cashier_id == cashier_id)
            count_query = count_query.where(CashRegisterSession.cashier_id == cashier_id)

        total = (await self.db.execute(count_query)).scalar_one()
        query = query.order_by(CashRegisterSession.opened_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def create_session(self, session: CashRegisterSession) -> CashRegisterSession:
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def save_session(self, session: CashRegisterSession) -> CashRegisterSession:
        await self.db.flush()
        await self.db.refresh(session)
        return session

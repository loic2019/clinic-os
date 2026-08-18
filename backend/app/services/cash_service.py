"""Cash register session business logic (spec sections 19-20, 24)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ClinicOSException, ConflictError, NotFoundError
from app.models.cash import CashRegisterSession, CashSessionStatus
from app.repositories.cash_repository import CashRepository
from app.repositories.payment_repository import PaymentRepository
from app.schemas.cash import CashSessionClose, CashSessionOpen


class CashService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.cash = CashRepository(db)
        self.payments = PaymentRepository(db)

    async def list_registers(self):
        return await self.cash.list_registers()

    async def open_session(self, payload: CashSessionOpen, *, cashier_id: uuid.UUID) -> CashRegisterSession:
        register = await self.cash.get_register_by_id(payload.cash_register_id)
        if register is None:
            raise NotFoundError("Caisse introuvable.")

        if await self.cash.get_open_session_for_user(cashier_id):
            raise ConflictError("Vous avez déjà une session de caisse ouverte.")
        if await self.cash.get_open_session_for_register(payload.cash_register_id):
            raise ConflictError("Cette caisse a déjà une session ouverte par un autre utilisateur.")

        session = CashRegisterSession(
            cash_register_id=payload.cash_register_id,
            cashier_id=cashier_id,
            opened_at=datetime.now(timezone.utc),
            opening_balance=payload.opening_balance,
        )
        return await self.cash.create_session(session)

    async def get_session(self, session_id: uuid.UUID) -> CashRegisterSession:
        session = await self.cash.get_session_by_id(session_id)
        if session is None:
            raise NotFoundError("Session de caisse introuvable.")
        return session

    async def get_my_open_session(self, cashier_id: uuid.UUID) -> CashRegisterSession | None:
        return await self.cash.get_open_session_for_user(cashier_id)

    async def list_sessions(self, *, page: int, page_size: int, cashier_id: uuid.UUID | None):
        return await self.cash.list_paginated(page=page, page_size=page_size, cashier_id=cashier_id)

    async def close_session(self, session_id: uuid.UUID, payload: CashSessionClose) -> CashRegisterSession:
        session = await self.get_session(session_id)
        if session.status != CashSessionStatus.OPEN:
            raise ConflictError("Cette session n'est pas ouverte.")

        collected = await self.payments.sum_active_amount_for_session(session_id)
        expected_balance = round(float(session.opening_balance) + collected, 2)
        difference = round(payload.closing_balance - expected_balance, 2)

        if difference != 0 and not payload.difference_justification:
            raise ClinicOSException(
                f"Écart de caisse détecté ({difference:+.2f}). Une justification est requise pour clôturer.",
                code="CASH_DISCREPANCY",
            )

        session.closing_balance = payload.closing_balance
        session.expected_balance = expected_balance
        session.difference = difference
        session.difference_justification = payload.difference_justification
        session.closed_at = datetime.now(timezone.utc)
        session.status = CashSessionStatus.CLOSED

        return await self.cash.save_session(session)

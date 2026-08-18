"""Payment business logic (spec sections 21-23, 27)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.billing import InvoiceStatus
from app.models.payment import Payment, PaymentStatus, RefundRequest, RefundStatus
from app.repositories.billing_repository import InvoiceRepository
from app.repositories.cash_repository import CashRepository
from app.repositories.payment_repository import PaymentRepository
from app.schemas.payment import PaymentCreate, RefundRequestCreate
from app.services.accounting_service import AccountingService
from app.services.numbering_service import generate_number

PAYMENT_NUMBER_KEY = "PAY"
PAYMENT_NUMBER_PREFIX = "PAY"


class PaymentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.payments = PaymentRepository(db)
        self.invoices = InvoiceRepository(db)
        self.cash = CashRepository(db)
        self.accounting = AccountingService(db)

    async def record_payment(self, payload: PaymentCreate, *, cashier_id: uuid.UUID | None) -> Payment:
        invoice = await self.invoices.get_by_id(payload.invoice_id)
        if invoice is None:
            raise NotFoundError("Facture introuvable.")
        if invoice.status in (InvoiceStatus.CANCELLED, InvoiceStatus.VOIDED):
            raise ConflictError("Impossible d'encaisser une facture annulée.")
        if invoice.status == InvoiceStatus.PAID:
            raise ConflictError("Cette facture est déjà entièrement payée.")
        if payload.amount > invoice.balance_due + 0.01:  # tolerate rounding
            raise ConflictError(
                f"Le montant ({payload.amount}) dépasse le solde dû ({invoice.balance_due})."
            )

        # A cashier normally must have an open till to take money, so
        # every cash-register payment is traceable to a session (spec
        # section 17). Payments recorded by an admin/accountant without
        # an open session (e.g. reconciling later) are still allowed —
        # cash_session_id is simply left null in that case.
        open_session = None
        if cashier_id:
            open_session = await self.cash.get_open_session_for_user(cashier_id)

        payment_number = await generate_number(self.db, key=PAYMENT_NUMBER_KEY, prefix=PAYMENT_NUMBER_PREFIX)

        payment = Payment(
            payment_number=payment_number,
            invoice_id=invoice.id,
            patient_id=invoice.patient_id,
            cashier_id=cashier_id,
            cash_session_id=open_session.id if open_session else None,
            method=payload.method,
            amount=payload.amount,
            reference=payload.reference,
        )
        created = await self.payments.create(payment)

        # Automatic accounting entry (spec section 35's example: DEBIT
        # Caisse / CREDIT Recettes médicales). Runs in the same
        # transaction as the payment — if this fails, the whole payment
        # rolls back rather than leaving cash collected with no ledger
        # trace.
        await self.accounting.record_payment_entry(
            payment_id=created.id,
            amount=float(payload.amount),
            description=f"Paiement {payment_number} — facture {invoice.invoice_number}",
            created_by_id=cashier_id,
        )

        # Recompute invoice status from the fresh payment total. `invoice`
        # is already in the session identity map with its `payments`
        # collection loaded from before this payment existed — the new
        # row is committed, but that in-memory collection won't reflect
        # it without an explicit refresh (same class of bug as the
        # medical-act price history staleness fixed in Phase 4).
        await self.db.refresh(invoice, attribute_names=["payments"])
        if invoice.balance_due <= 0.01:
            invoice.status = InvoiceStatus.PAID
        elif invoice.amount_paid > 0:
            invoice.status = InvoiceStatus.PARTIALLY_PAID
        await self.invoices.save(invoice)

        return await self.payments.get_by_id(created.id)

    async def get_payment(self, payment_id: uuid.UUID) -> Payment:
        payment = await self.payments.get_by_id(payment_id)
        if payment is None:
            raise NotFoundError("Paiement introuvable.")
        return payment

    async def list_payments(
        self, *, page: int, page_size: int, invoice_id: uuid.UUID | None, cashier_id: uuid.UUID | None
    ):
        return await self.payments.list_paginated(
            page=page, page_size=page_size, invoice_id=invoice_id, cashier_id=cashier_id
        )

    async def request_refund(
        self, payment_id: uuid.UUID, payload: RefundRequestCreate, *, requested_by_id: uuid.UUID | None
    ) -> RefundRequest:
        payment = await self.get_payment(payment_id)
        if payment.status != PaymentStatus.ACTIVE:
            raise ConflictError("Ce paiement n'est pas actif.")
        if payload.amount > float(payment.amount) + 0.01:
            raise ConflictError("Le montant du remboursement dépasse le montant payé.")

        request = RefundRequest(
            payment_id=payment.id, requested_by_id=requested_by_id, reason=payload.reason, amount=payload.amount
        )
        self.db.add(request)
        await self.db.flush()
        await self.db.refresh(request)
        return request

    async def review_refund(
        self, request_id: uuid.UUID, *, approve: bool, review_notes: str | None, reviewed_by_id: uuid.UUID | None
    ) -> RefundRequest:
        request = await self.payments.get_refund_request(request_id)
        if request is None:
            raise NotFoundError("Demande de remboursement introuvable.")
        if request.status != RefundStatus.PENDING:
            raise ConflictError("Cette demande a déjà été traitée.")

        request.status = RefundStatus.APPROVED if approve else RefundStatus.REJECTED
        request.reviewed_by_id = reviewed_by_id
        request.reviewed_at = datetime.now(timezone.utc)
        request.review_notes = review_notes

        if approve:
            payment = await self.get_payment(request.payment_id)
            payment.status = PaymentStatus.VOIDED
            await self.payments.save(payment)

            await self.accounting.record_refund_entry(
                payment_id=payment.id,
                amount=float(request.amount),
                description=f"Remboursement paiement {payment.payment_number}",
                created_by_id=reviewed_by_id,
            )

            invoice = await self.invoices.get_by_id(payment.invoice_id)
            if invoice.amount_paid <= 0:
                invoice.status = InvoiceStatus.UNPAID
            elif invoice.balance_due > 0.01:
                invoice.status = InvoiceStatus.PARTIALLY_PAID
            await self.invoices.save(invoice)

        await self.db.flush()
        return request

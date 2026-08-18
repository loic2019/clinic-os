"""Invoice business logic (spec sections 15-18, 25-26)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ClinicOSException, ConflictError, ForbiddenError, NotFoundError
from app.models.billing import (
    CancellationRequest,
    CancellationStatus,
    Invoice,
    InvoiceItem,
    InvoiceStatus,
)
from app.repositories.billing_repository import InvoiceRepository
from app.repositories.medical_act_repository import MedicalActRepository
from app.repositories.patient_repository import PatientRepository
from app.schemas.billing import CancellationRequestCreate, InvoiceCreate
from app.services.numbering_service import generate_number

INVOICE_NUMBER_KEY = "FAC"
INVOICE_NUMBER_PREFIX = "FAC"


class InvoiceService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.invoices = InvoiceRepository(db)
        self.medical_acts = MedicalActRepository(db)
        self.patients = PatientRepository(db)

    async def create_invoice(self, payload: InvoiceCreate, *, created_by_id: uuid.UUID | None) -> Invoice:
        patient = await self.patients.get_by_id(payload.patient_id, include_archived=False)
        if patient is None:
            raise NotFoundError("Patient introuvable.")

        invoice_number = await generate_number(self.db, key=INVOICE_NUMBER_KEY, prefix=INVOICE_NUMBER_PREFIX)

        invoice = Invoice(
            invoice_number=invoice_number,
            patient_id=payload.patient_id,
            created_by_id=created_by_id,
            discount_amount=payload.discount_amount,
            notes=payload.notes,
        )

        # --- Server-side calculation only (spec section 15): the client
        # never sends a price directly for a catalog item — the price
        # actually charged is always looked up and snapshotted here. ---
        for item_input in payload.items:
            if item_input.medical_act_id:
                act = await self.medical_acts.get_by_id(item_input.medical_act_id)
                if act is None:
                    raise NotFoundError(f"Acte médical introuvable : {item_input.medical_act_id}")
                current_price = act.current_price
                if current_price is None:
                    raise ClinicOSException(
                        f"L'acte '{act.name}' n'a aucun prix en vigueur.", code="NO_PRICE"
                    )
                unit_price = float(current_price.price)
                tax_rate = float(act.tax_rate)
                description = act.name
            else:
                if not item_input.description or item_input.unit_price is None:
                    raise ClinicOSException(
                        "description et unit_price sont requis pour une ligne libre (sans acte catalogue).",
                        code="INVALID_ITEM",
                    )
                unit_price = item_input.unit_price
                tax_rate = 0.0
                description = item_input.description

            line_total = round(item_input.quantity * unit_price * (1 + tax_rate / 100), 2)

            invoice.items.append(
                InvoiceItem(
                    item_type=item_input.item_type,
                    medical_act_id=item_input.medical_act_id,
                    description=description,
                    quantity=item_input.quantity,
                    unit_price=unit_price,
                    tax_rate=tax_rate,
                    line_total=line_total,
                )
            )

        created = await self.invoices.create(invoice)
        return await self.invoices.get_by_id(created.id)

    async def get_invoice(self, invoice_id: uuid.UUID) -> Invoice:
        invoice = await self.invoices.get_by_id(invoice_id)
        if invoice is None:
            raise NotFoundError("Facture introuvable.")
        return invoice

    async def list_invoices(
        self,
        *,
        page: int,
        page_size: int,
        cashier_id: uuid.UUID | None,
        patient_id: uuid.UUID | None,
        status: str | None,
        date_from,
        date_to,
    ):
        return await self.invoices.list_paginated(
            page=page,
            page_size=page_size,
            cashier_id=cashier_id,
            patient_id=patient_id,
            status=status,
            date_from=date_from,
            date_to=date_to,
        )

    async def request_cancellation(
        self, invoice_id: uuid.UUID, payload: CancellationRequestCreate, *, requested_by_id: uuid.UUID | None
    ) -> CancellationRequest:
        invoice = await self.get_invoice(invoice_id)
        if invoice.status in (InvoiceStatus.CANCELLED, InvoiceStatus.VOIDED):
            raise ConflictError("Cette facture est déjà annulée.")

        request = CancellationRequest(
            invoice_id=invoice.id, requested_by_id=requested_by_id, reason=payload.reason
        )
        self.db.add(request)
        await self.db.flush()
        await self.db.refresh(request)
        return request

    async def review_cancellation(
        self, request_id: uuid.UUID, *, approve: bool, review_notes: str | None, reviewed_by_id: uuid.UUID | None
    ) -> CancellationRequest:
        request = await self.invoices.get_cancellation_request(request_id)
        if request is None:
            raise NotFoundError("Demande d'annulation introuvable.")
        if request.status != CancellationStatus.PENDING:
            raise ConflictError("Cette demande a déjà été traitée.")

        request.status = CancellationStatus.APPROVED if approve else CancellationStatus.REJECTED
        request.reviewed_by_id = reviewed_by_id
        request.reviewed_at = datetime.now(timezone.utc)
        request.review_notes = review_notes

        if approve:
            invoice = await self.get_invoice(request.invoice_id)
            invoice.status = InvoiceStatus.CANCELLED
            await self.invoices.save(invoice)

        await self.db.flush()
        return request

"""
GET  /api/invoices                          list, filter by cashier/patient/status/date ("Mes factures")
POST /api/invoices                            create (server-side price calculation)
GET  /api/invoices/{id}
POST /api/invoices/{id}/cancellation-requests  request cancellation
POST /api/invoices/cancellation-requests/{id}/review  admin approve/reject
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user, require_permission
from app.models.user import User
from app.schemas.billing import (
    CancellationRequestCreate,
    CancellationRequestRead,
    CancellationRequestReview,
    InvoiceCreate,
    InvoiceListItem,
    InvoiceListResponse,
    InvoiceRead,
)
from app.services.billing_service import InvoiceService

router = APIRouter(prefix="/invoices")


@router.get("", response_model=None, dependencies=[Depends(require_permission("billing.read"))])
async def list_invoices(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    mine_only: bool = Query(default=False, description="'Mes factures' — spec section 18"),
    patient_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = InvoiceService(db)
    cashier_id = current_user.id if mine_only else None
    items, total = await service.list_invoices(
        page=page,
        page_size=page_size,
        cashier_id=cashier_id,
        patient_id=patient_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
    )
    data = InvoiceListResponse(
        items=[InvoiceListItem.model_validate(i) for i in items], total=total, page=page, page_size=page_size
    )
    return {"success": True, "data": data, "message": "OK"}


@router.post("", response_model=None, dependencies=[Depends(require_permission("billing.create"))])
async def create_invoice(
    payload: InvoiceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = InvoiceService(db)
    invoice = await service.create_invoice(payload, created_by_id=current_user.id)
    await db.commit()
    return {
        "success": True,
        "data": InvoiceRead.model_validate(invoice),
        "message": f"Facture {invoice.invoice_number} créée.",
    }


@router.get("/{invoice_id}", response_model=None, dependencies=[Depends(require_permission("billing.read"))])
async def get_invoice(invoice_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = InvoiceService(db)
    invoice = await service.get_invoice(invoice_id)
    return {"success": True, "data": InvoiceRead.model_validate(invoice), "message": "OK"}


@router.post(
    "/{invoice_id}/cancellation-requests",
    response_model=None,
    dependencies=[Depends(require_permission("invoice.cancel_request"))],
)
async def request_cancellation(
    invoice_id: uuid.UUID,
    payload: CancellationRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = InvoiceService(db)
    request = await service.request_cancellation(invoice_id, payload, requested_by_id=current_user.id)
    await db.commit()
    return {
        "success": True,
        "data": CancellationRequestRead.model_validate(request),
        "message": "Demande d'annulation envoyée.",
    }


@router.post(
    "/cancellation-requests/{request_id}/review",
    response_model=None,
    dependencies=[Depends(require_permission("invoice.cancel_approve"))],
)
async def review_cancellation(
    request_id: uuid.UUID,
    payload: CancellationRequestReview,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = InvoiceService(db)
    request = await service.review_cancellation(
        request_id, approve=payload.approve, review_notes=payload.review_notes, reviewed_by_id=current_user.id
    )
    await db.commit()
    message = "Annulation approuvée." if payload.approve else "Annulation rejetée."
    return {"success": True, "data": CancellationRequestRead.model_validate(request), "message": message}

"""
GET  /api/payments                        list, filter by invoice/cashier
POST /api/payments                          record a payment (updates invoice status)
GET  /api/payments/{id}
POST /api/payments/{id}/refund-requests      request a refund
POST /api/payments/refund-requests/{id}/review  admin approve/reject
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user, require_permission
from app.models.user import User
from app.schemas.payment import (
    PaymentCreate,
    PaymentListResponse,
    PaymentRead,
    RefundRequestCreate,
    RefundRequestRead,
    RefundRequestReview,
)
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/payments")


@router.get("", response_model=None, dependencies=[Depends(require_permission("payments.read"))])
async def list_payments(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    invoice_id: uuid.UUID | None = Query(default=None),
    mine_only: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = PaymentService(db)
    cashier_id = current_user.id if mine_only else None
    items, total = await service.list_payments(
        page=page, page_size=page_size, invoice_id=invoice_id, cashier_id=cashier_id
    )
    data = PaymentListResponse(
        items=[PaymentRead.model_validate(p) for p in items], total=total, page=page, page_size=page_size
    )
    return {"success": True, "data": data, "message": "OK"}


@router.post("", response_model=None, dependencies=[Depends(require_permission("payments.create"))])
async def record_payment(
    payload: PaymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = PaymentService(db)
    payment = await service.record_payment(payload, cashier_id=current_user.id)
    await db.commit()
    return {
        "success": True,
        "data": PaymentRead.model_validate(payment),
        "message": f"Paiement {payment.payment_number} enregistré.",
    }


@router.get("/{payment_id}", response_model=None, dependencies=[Depends(require_permission("payments.read"))])
async def get_payment(payment_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = PaymentService(db)
    payment = await service.get_payment(payment_id)
    return {"success": True, "data": PaymentRead.model_validate(payment), "message": "OK"}


@router.post(
    "/{payment_id}/refund-requests",
    response_model=None,
    dependencies=[Depends(require_permission("refund.request"))],
)
async def request_refund(
    payment_id: uuid.UUID,
    payload: RefundRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = PaymentService(db)
    request = await service.request_refund(payment_id, payload, requested_by_id=current_user.id)
    await db.commit()
    return {
        "success": True,
        "data": RefundRequestRead.model_validate(request),
        "message": "Demande de remboursement envoyée.",
    }


@router.post(
    "/refund-requests/{request_id}/review",
    response_model=None,
    dependencies=[Depends(require_permission("refund.approve"))],
)
async def review_refund(
    request_id: uuid.UUID,
    payload: RefundRequestReview,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = PaymentService(db)
    request = await service.review_refund(
        request_id, approve=payload.approve, review_notes=payload.review_notes, reviewed_by_id=current_user.id
    )
    await db.commit()
    message = "Remboursement approuvé." if payload.approve else "Remboursement rejeté."
    return {"success": True, "data": RefundRequestRead.model_validate(request), "message": message}

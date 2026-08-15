"""
GET  /api/laboratory/tests                              catalog list
POST /api/laboratory/tests                                catalog create
GET  /api/laboratory/tests/{id}
PUT  /api/laboratory/tests/{id}

GET  /api/laboratory/orders                              list orders
POST /api/laboratory/orders                                create order
GET  /api/laboratory/orders/{id}                            detail

POST /api/laboratory/orders/{id}/samples                   record sample collection
POST /api/laboratory/orders/{id}/items/{item_id}/result     enter a result
POST /api/laboratory/orders/{id}/items/{item_id}/validate   validate a result
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user, require_permission
from app.models.user import User
from app.schemas.laboratory import (
    LabOrderCreate,
    LabOrderListItem,
    LabOrderListResponse,
    LabOrderRead,
    LabResultInput,
    LabSampleCreate,
    LabTestCreate,
    LabTestListResponse,
    LabTestRead,
    LabTestUpdate,
)
from app.services.laboratory_service import LabOrderService, LabTestService

router = APIRouter(prefix="/laboratory")


# --- Catalog -------------------------------------------------------------


@router.get(
    "/tests", response_model=None, dependencies=[Depends(require_permission("laboratory.read"))]
)
async def list_lab_tests(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
):
    service = LabTestService(db)
    items, total = await service.list_tests(page=page, page_size=page_size, search=search, active_only=active_only)
    data = LabTestListResponse(
        items=[LabTestRead.model_validate(t) for t in items], total=total, page=page, page_size=page_size
    )
    return {"success": True, "data": data, "message": "OK"}


@router.post(
    "/tests", response_model=None, dependencies=[Depends(require_permission("laboratory.create"))]
)
async def create_lab_test(payload: LabTestCreate, db: AsyncSession = Depends(get_db)):
    service = LabTestService(db)
    test = await service.create_test(payload)
    await db.commit()
    return {"success": True, "data": LabTestRead.model_validate(test), "message": "Analyse ajoutée au catalogue."}


@router.get(
    "/tests/{test_id}", response_model=None, dependencies=[Depends(require_permission("laboratory.read"))]
)
async def get_lab_test(test_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = LabTestService(db)
    test = await service.get_test(test_id)
    return {"success": True, "data": LabTestRead.model_validate(test), "message": "OK"}


@router.put(
    "/tests/{test_id}", response_model=None, dependencies=[Depends(require_permission("laboratory.update"))]
)
async def update_lab_test(test_id: uuid.UUID, payload: LabTestUpdate, db: AsyncSession = Depends(get_db)):
    service = LabTestService(db)
    test = await service.update_test(test_id, payload)
    await db.commit()
    return {"success": True, "data": LabTestRead.model_validate(test), "message": "Analyse mise à jour."}


# --- Orders ------------------------------------------------------------------


@router.get(
    "/orders", response_model=None, dependencies=[Depends(require_permission("laboratory.read"))]
)
async def list_lab_orders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    patient_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    service = LabOrderService(db)
    items, total = await service.list_orders(page=page, page_size=page_size, patient_id=patient_id, status=status)
    data = LabOrderListResponse(
        items=[LabOrderListItem.model_validate(o) for o in items], total=total, page=page, page_size=page_size
    )
    return {"success": True, "data": data, "message": "OK"}


@router.post(
    "/orders", response_model=None, dependencies=[Depends(require_permission("laboratory.create"))]
)
async def create_lab_order(
    payload: LabOrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = LabOrderService(db)
    order = await service.create_order(payload, created_by_id=current_user.id)
    await db.commit()
    return {
        "success": True,
        "data": LabOrderRead.model_validate(order),
        "message": f"Commande {order.order_number} créée.",
    }


@router.get(
    "/orders/{order_id}", response_model=None, dependencies=[Depends(require_permission("laboratory.read"))]
)
async def get_lab_order(order_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = LabOrderService(db)
    order = await service.get_order(order_id)
    return {"success": True, "data": LabOrderRead.model_validate(order), "message": "OK"}


@router.post(
    "/orders/{order_id}/samples",
    response_model=None,
    dependencies=[Depends(require_permission("laboratory.update"))],
)
async def add_sample(
    order_id: uuid.UUID,
    payload: LabSampleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = LabOrderService(db)
    order = await service.add_sample(order_id, payload, collected_by_id=current_user.id)
    await db.commit()
    return {"success": True, "data": LabOrderRead.model_validate(order), "message": "Prélèvement enregistré."}


@router.post(
    "/orders/{order_id}/items/{item_id}/result",
    response_model=None,
    dependencies=[Depends(require_permission("laboratory.update"))],
)
async def enter_result(
    order_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: LabResultInput,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = LabOrderService(db)
    order = await service.enter_result(order_id, item_id, payload, entered_by_id=current_user.id)
    await db.commit()
    return {"success": True, "data": LabOrderRead.model_validate(order), "message": "Résultat enregistré."}


@router.post(
    "/orders/{order_id}/items/{item_id}/validate",
    response_model=None,
    dependencies=[Depends(require_permission("laboratory.validate"))],
)
async def validate_result(
    order_id: uuid.UUID,
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = LabOrderService(db)
    order = await service.validate_result(order_id, item_id, validated_by_id=current_user.id)
    await db.commit()
    return {"success": True, "data": LabOrderRead.model_validate(order), "message": "Résultat validé."}

"""
GET  /api/suppliers
POST /api/suppliers
GET  /api/suppliers/{id}
PUT  /api/suppliers/{id}

GET  /api/purchase-orders
POST /api/purchase-orders
GET  /api/purchase-orders/{id}
POST /api/purchase-orders/{id}/receive        receive items -> updates inventory
POST /api/purchase-orders/{id}/cancel
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user, require_permission
from app.models.user import User
from app.schemas.supplier import (
    PurchaseOrderCreate,
    PurchaseOrderListItem,
    PurchaseOrderListResponse,
    PurchaseOrderRead,
    ReceiveOrderInput,
    SupplierCreate,
    SupplierListResponse,
    SupplierRead,
    SupplierUpdate,
)
from app.services.supplier_service import PurchaseOrderService, SupplierService

router = APIRouter()

suppliers_router = APIRouter(prefix="/suppliers")
purchase_orders_router = APIRouter(prefix="/purchase-orders")


# --- Suppliers -----------------------------------------------------------


@suppliers_router.get("", response_model=None, dependencies=[Depends(require_permission("suppliers.read"))])
async def list_suppliers(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
):
    service = SupplierService(db)
    items, total = await service.list_suppliers(page=page, page_size=page_size, search=search, active_only=active_only)
    data = SupplierListResponse(
        items=[SupplierRead.model_validate(s) for s in items], total=total, page=page, page_size=page_size
    )
    return {"success": True, "data": data, "message": "OK"}


@suppliers_router.post("", response_model=None, dependencies=[Depends(require_permission("suppliers.create"))])
async def create_supplier(payload: SupplierCreate, db: AsyncSession = Depends(get_db)):
    service = SupplierService(db)
    supplier = await service.create_supplier(payload)
    await db.commit()
    return {"success": True, "data": SupplierRead.model_validate(supplier), "message": "Fournisseur créé."}


@suppliers_router.get(
    "/{supplier_id}", response_model=None, dependencies=[Depends(require_permission("suppliers.read"))]
)
async def get_supplier(supplier_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = SupplierService(db)
    supplier = await service.get_supplier(supplier_id)
    return {"success": True, "data": SupplierRead.model_validate(supplier), "message": "OK"}


@suppliers_router.put(
    "/{supplier_id}", response_model=None, dependencies=[Depends(require_permission("suppliers.update"))]
)
async def update_supplier(supplier_id: uuid.UUID, payload: SupplierUpdate, db: AsyncSession = Depends(get_db)):
    service = SupplierService(db)
    supplier = await service.update_supplier(supplier_id, payload)
    await db.commit()
    return {"success": True, "data": SupplierRead.model_validate(supplier), "message": "Fournisseur mis à jour."}


# --- Purchase orders -----------------------------------------------------------


@purchase_orders_router.get(
    "", response_model=None, dependencies=[Depends(require_permission("suppliers.read"))]
)
async def list_purchase_orders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    supplier_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    service = PurchaseOrderService(db)
    items, total = await service.list_orders(page=page, page_size=page_size, supplier_id=supplier_id, status=status)
    data = PurchaseOrderListResponse(
        items=[PurchaseOrderListItem.model_validate(o) for o in items], total=total, page=page, page_size=page_size
    )
    return {"success": True, "data": data, "message": "OK"}


@purchase_orders_router.post(
    "", response_model=None, dependencies=[Depends(require_permission("suppliers.create"))]
)
async def create_purchase_order(
    payload: PurchaseOrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = PurchaseOrderService(db)
    order = await service.create_order(payload, created_by_id=current_user.id)
    await db.commit()
    return {
        "success": True,
        "data": PurchaseOrderRead.model_validate(order),
        "message": f"Commande {order.order_number} créée.",
    }


@purchase_orders_router.get(
    "/{order_id}", response_model=None, dependencies=[Depends(require_permission("suppliers.read"))]
)
async def get_purchase_order(order_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = PurchaseOrderService(db)
    order = await service.get_order(order_id)
    return {"success": True, "data": PurchaseOrderRead.model_validate(order), "message": "OK"}


@purchase_orders_router.post(
    "/{order_id}/receive",
    response_model=None,
    dependencies=[Depends(require_permission("suppliers.update"))],
)
async def receive_purchase_order(
    order_id: uuid.UUID,
    payload: ReceiveOrderInput,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = PurchaseOrderService(db)
    order = await service.receive_order(order_id, payload, received_by_id=current_user.id)
    await db.commit()
    return {
        "success": True,
        "data": PurchaseOrderRead.model_validate(order),
        "message": "Réception enregistrée, stock mis à jour.",
    }


@purchase_orders_router.post(
    "/{order_id}/cancel",
    response_model=None,
    dependencies=[Depends(require_permission("suppliers.update"))],
)
async def cancel_purchase_order(order_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = PurchaseOrderService(db)
    order = await service.cancel_order(order_id)
    await db.commit()
    return {"success": True, "data": PurchaseOrderRead.model_validate(order), "message": "Commande annulée."}


router.include_router(suppliers_router)
router.include_router(purchase_orders_router)

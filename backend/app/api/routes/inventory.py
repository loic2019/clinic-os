"""
GET  /api/inventory/items                  catalog list
POST /api/inventory/items                    catalog create
GET  /api/inventory/items/{id}
PUT  /api/inventory/items/{id}

POST /api/inventory/items/{id}/movements     record a movement (dispensation, adjustment, ...)
GET  /api/inventory/movements                list movements

GET  /api/inventory/alerts                   low-stock + expiring/expired batches
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user, require_permission
from app.models.user import User
from app.schemas.inventory import (
    InventoryAlerts,
    InventoryItemCreate,
    InventoryItemListResponse,
    InventoryItemRead,
    InventoryItemUpdate,
    MovementCreate,
    MovementListResponse,
    MovementRead,
)
from app.services.inventory_service import InventoryService

router = APIRouter(prefix="/inventory")


@router.get("/items", response_model=None, dependencies=[Depends(require_permission("inventory.read"))])
async def list_items(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    category: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
):
    service = InventoryService(db)
    items, total = await service.list_items(page=page, page_size=page_size, search=search, category=category, active_only=active_only)
    data = InventoryItemListResponse(
        items=[InventoryItemRead.model_validate(i) for i in items], total=total, page=page, page_size=page_size
    )
    return {"success": True, "data": data, "message": "OK"}


@router.post("/items", response_model=None, dependencies=[Depends(require_permission("inventory.create"))])
async def create_item(payload: InventoryItemCreate, db: AsyncSession = Depends(get_db)):
    service = InventoryService(db)
    item = await service.create_item(payload)
    await db.commit()
    return {"success": True, "data": InventoryItemRead.model_validate(item), "message": "Article créé."}


@router.get("/items/{item_id}", response_model=None, dependencies=[Depends(require_permission("inventory.read"))])
async def get_item(item_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = InventoryService(db)
    item = await service.get_item(item_id)
    return {"success": True, "data": InventoryItemRead.model_validate(item), "message": "OK"}


@router.put("/items/{item_id}", response_model=None, dependencies=[Depends(require_permission("inventory.update"))])
async def update_item(item_id: uuid.UUID, payload: InventoryItemUpdate, db: AsyncSession = Depends(get_db)):
    service = InventoryService(db)
    item = await service.update_item(item_id, payload)
    await db.commit()
    return {"success": True, "data": InventoryItemRead.model_validate(item), "message": "Article mis à jour."}


@router.post(
    "/items/{item_id}/movements",
    response_model=None,
    dependencies=[Depends(require_permission("inventory.update"))],
)
async def record_movement(
    item_id: uuid.UUID,
    payload: MovementCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = InventoryService(db)
    item = await service.record_movement(item_id, payload, created_by_id=current_user.id)
    await db.commit()
    return {"success": True, "data": InventoryItemRead.model_validate(item), "message": "Mouvement enregistré."}


@router.get("/movements", response_model=None, dependencies=[Depends(require_permission("inventory.read"))])
async def list_movements(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    item_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    service = InventoryService(db)
    items, total = await service.list_movements(page=page, page_size=page_size, item_id=item_id)
    data = MovementListResponse(
        items=[MovementRead.model_validate(m) for m in items], total=total, page=page, page_size=page_size
    )
    return {"success": True, "data": data, "message": "OK"}


@router.get("/alerts", response_model=None, dependencies=[Depends(require_permission("inventory.read"))])
async def get_alerts(
    expiry_horizon_days: int = Query(default=30, ge=1, le=365), db: AsyncSession = Depends(get_db)
):
    service = InventoryService(db)
    alerts = await service.get_alerts(expiry_horizon_days=expiry_horizon_days)
    return {"success": True, "data": alerts, "message": "OK"}

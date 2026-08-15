"""
GET    /api/users
POST   /api/users
GET    /api/users/{id}
PUT    /api/users/{id}
DELETE /api/users/{id}   (deactivate, never a hard delete — spec section 25)

All routes require the matching `users.*` permission (spec section 29).
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import require_permission
from app.schemas.user import UserCreate, UserListResponse, UserRead, UserUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/users")


@router.get("", response_model=None, dependencies=[Depends(require_permission("users.read"))])
async def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db)
    items, total = await service.list_users(page=page, page_size=page_size, search=search)
    data = UserListResponse(
        items=[UserRead.model_validate(u) for u in items],
        total=total,
        page=page,
        page_size=page_size,
    )
    return {"success": True, "data": data, "message": "OK"}


@router.post("", response_model=None, dependencies=[Depends(require_permission("users.create"))])
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    service = UserService(db)
    user = await service.create_user(payload)
    await db.commit()
    return {
        "success": True,
        "data": UserRead.model_validate(user),
        "message": "Utilisateur créé.",
    }


@router.get(
    "/{user_id}", response_model=None, dependencies=[Depends(require_permission("users.read"))]
)
async def get_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = UserService(db)
    user = await service.get_user(user_id)
    return {"success": True, "data": UserRead.model_validate(user), "message": "OK"}


@router.put(
    "/{user_id}", response_model=None, dependencies=[Depends(require_permission("users.update"))]
)
async def update_user(user_id: uuid.UUID, payload: UserUpdate, db: AsyncSession = Depends(get_db)):
    service = UserService(db)
    user = await service.update_user(user_id, payload)
    await db.commit()
    return {
        "success": True,
        "data": UserRead.model_validate(user),
        "message": "Utilisateur mis à jour.",
    }


@router.delete(
    "/{user_id}", response_model=None, dependencies=[Depends(require_permission("users.update"))]
)
async def deactivate_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = UserService(db)
    user = await service.deactivate_user(user_id)
    await db.commit()
    return {
        "success": True,
        "data": UserRead.model_validate(user),
        "message": "Utilisateur désactivé.",
    }

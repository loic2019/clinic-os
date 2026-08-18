"""
GET  /api/cash/registers                  list active registers
GET  /api/cash/sessions                    list sessions
POST /api/cash/sessions/open                open a session
GET  /api/cash/sessions/mine                current user's open session, if any
GET  /api/cash/sessions/{id}
POST /api/cash/sessions/{id}/close           close a session (spec section 24)
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user, require_permission
from app.models.user import User
from app.schemas.cash import (
    CashRegisterRead,
    CashSessionClose,
    CashSessionListResponse,
    CashSessionOpen,
    CashSessionRead,
)
from app.services.cash_service import CashService

router = APIRouter(prefix="/cash")


@router.get("/registers", response_model=None, dependencies=[Depends(require_permission("cash.open"))])
async def list_registers(db: AsyncSession = Depends(get_db)):
    service = CashService(db)
    registers = await service.list_registers()
    return {
        "success": True,
        "data": [CashRegisterRead.model_validate(r) for r in registers],
        "message": "OK",
    }


@router.get("/sessions", response_model=None, dependencies=[Depends(require_permission("cash.open"))])
async def list_sessions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    mine_only: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CashService(db)
    cashier_id = current_user.id if mine_only else None
    items, total = await service.list_sessions(page=page, page_size=page_size, cashier_id=cashier_id)
    data = CashSessionListResponse(
        items=[CashSessionRead.model_validate(s) for s in items], total=total, page=page, page_size=page_size
    )
    return {"success": True, "data": data, "message": "OK"}


@router.get("/sessions/mine", response_model=None, dependencies=[Depends(require_permission("cash.open"))])
async def get_my_open_session(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    service = CashService(db)
    session = await service.get_my_open_session(current_user.id)
    return {
        "success": True,
        "data": CashSessionRead.model_validate(session) if session else None,
        "message": "OK",
    }


@router.post("/sessions/open", response_model=None, dependencies=[Depends(require_permission("cash.open"))])
async def open_session(
    payload: CashSessionOpen,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CashService(db)
    session = await service.open_session(payload, cashier_id=current_user.id)
    await db.commit()
    return {"success": True, "data": CashSessionRead.model_validate(session), "message": "Caisse ouverte."}


@router.get("/sessions/{session_id}", response_model=None, dependencies=[Depends(require_permission("cash.open"))])
async def get_session(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = CashService(db)
    session = await service.get_session(session_id)
    return {"success": True, "data": CashSessionRead.model_validate(session), "message": "OK"}


@router.post(
    "/sessions/{session_id}/close", response_model=None, dependencies=[Depends(require_permission("cash.close"))]
)
async def close_session(session_id: uuid.UUID, payload: CashSessionClose, db: AsyncSession = Depends(get_db)):
    service = CashService(db)
    session = await service.close_session(session_id, payload)
    await db.commit()
    message = "Caisse clôturée." if session.difference == 0 else f"Caisse clôturée avec un écart de {session.difference:+.2f}."
    return {"success": True, "data": CashSessionRead.model_validate(session), "message": message}

"""
POST /api/auth/login
POST /api/auth/refresh
POST /api/auth/logout
GET  /api/auth/me
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.auth import CurrentUser, LoginRequest, LogoutRequest, RefreshRequest, TokenResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth")


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None
    return user_agent, ip_address


@router.post("/login", response_model=None)
async def login(payload: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    user = await service.authenticate(payload.username, payload.password)

    user_agent, ip_address = _client_meta(request)
    access_token, refresh_token, expires_in = await service.issue_tokens(
        user, user_agent=user_agent, ip_address=ip_address
    )
    await db.commit()

    token_response = TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )
    return {"success": True, "data": token_response, "message": "Connexion réussie."}


@router.post("/refresh", response_model=None)
async def refresh(payload: RefreshRequest, request: Request, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    user_agent, ip_address = _client_meta(request)

    access_token, refresh_token, expires_in = await service.refresh(
        payload.refresh_token, user_agent=user_agent, ip_address=ip_address
    )
    await db.commit()

    token_response = TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )
    return {"success": True, "data": token_response, "message": "Jeton rafraîchi."}


@router.post("/logout", response_model=None)
async def logout(
    payload: LogoutRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = AuthService(db)
    await service.logout(current_user.id, payload.refresh_token)
    await db.commit()
    return {"success": True, "data": None, "message": "Déconnexion réussie."}


@router.get("/me", response_model=None)
async def me(current_user: User = Depends(get_current_user)):
    profile = CurrentUser(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        roles=current_user.role_names,
        permissions=sorted(current_user.permission_codes),
    )
    return {"success": True, "data": profile, "message": "OK"}

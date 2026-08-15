"""
FastAPI dependencies enforcing authentication and RBAC.

This is the backend-side enforcement point required by spec section 30:
the frontend is never trusted — every protected route depends on
`get_current_user` (valid JWT) and, where relevant,
`require_permission("module.action")` (role must grant that permission).
"""

import uuid

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.models.user import User
from app.repositories.user_repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if token is None:
        raise UnauthorizedError("Authentification requise.")

    try:
        payload = decode_access_token(token)
    except JWTError:
        raise UnauthorizedError("Jeton invalide ou expiré.")

    user_id = payload.get("sub")
    if user_id is None:
        raise UnauthorizedError("Jeton invalide.")

    user = await UserRepository(db).get_by_id(uuid.UUID(user_id))
    if user is None or not user.is_active:
        raise UnauthorizedError("Compte utilisateur introuvable ou désactivé.")

    return user


def require_permission(permission_code: str):
    """
    Usage:
        @router.get("/patients", dependencies=[Depends(require_permission("patients.read"))])
    """

    async def _check(current_user: User = Depends(get_current_user)) -> User:
        if permission_code not in current_user.permission_codes:
            raise ForbiddenError(
                f"Permission insuffisante : '{permission_code}' est requise pour cette action."
            )
        return current_user

    return _check


def require_role(*role_names: str):
    async def _check(current_user: User = Depends(get_current_user)) -> User:
        if not set(role_names) & set(current_user.role_names):
            raise ForbiddenError(
                f"Rôle insuffisant : un des rôles {list(role_names)} est requis."
            )
        return current_user

    return _check

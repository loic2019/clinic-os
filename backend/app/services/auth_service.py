"""
Authentication business logic: login, token refresh, logout.

Kept deliberately independent of FastAPI request/response objects so it
can be unit-tested and reused (e.g. from Clinic AI or a future mobile
API) without pulling in HTTP concerns.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UnauthorizedError
from app.core.security import (
    create_access_token,
    generate_refresh_token_value,
    hash_refresh_token,
    refresh_token_expiry,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.user_repository import UserRepository


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.users = UserRepository(db)

    async def authenticate(self, username: str, password: str) -> User:
        user = await self.users.get_by_username(username)
        if user is None or not verify_password(password, user.hashed_password):
            # Same error for "no such user" and "wrong password": do not
            # leak which one it was.
            raise UnauthorizedError("Nom d'utilisateur ou mot de passe incorrect.")
        if not user.is_active:
            raise UnauthorizedError("Ce compte est désactivé.")
        return user

    async def issue_tokens(
        self, user: User, *, user_agent: str | None = None, ip_address: str | None = None
    ) -> tuple[str, str, int]:
        from app.core.config import settings

        access_token = create_access_token(
            user_id=user.id,
            username=user.username,
            roles=user.role_names,
            permissions=sorted(user.permission_codes),
        )

        raw_refresh = generate_refresh_token_value()
        refresh_record = RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(raw_refresh),
            expires_at=refresh_token_expiry(),
            user_agent=user_agent,
            ip_address=ip_address,
        )
        self.db.add(refresh_record)

        user.last_login_at = datetime.now(timezone.utc)
        await self.db.flush()

        return access_token, raw_refresh, settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    async def refresh(
        self, raw_refresh_token: str, *, user_agent: str | None = None, ip_address: str | None = None
    ) -> tuple[str, str, int]:
        token_hash = hash_refresh_token(raw_refresh_token)
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        record = result.scalar_one_or_none()

        if record is None or not record.is_active:
            raise UnauthorizedError("Refresh token invalide ou expiré.")

        user = await self.users.get_by_id(record.user_id)
        if user is None or not user.is_active:
            raise UnauthorizedError("Compte utilisateur introuvable ou désactivé.")

        # Rotate: revoke the used refresh token and issue a brand new pair.
        record.revoked_at = datetime.now(timezone.utc)
        await self.db.flush()

        return await self.issue_tokens(user, user_agent=user_agent, ip_address=ip_address)

    async def logout(self, user_id: uuid.UUID, raw_refresh_token: str | None = None) -> None:
        now = datetime.now(timezone.utc)

        if raw_refresh_token:
            token_hash = hash_refresh_token(raw_refresh_token)
            result = await self.db.execute(
                select(RefreshToken).where(
                    RefreshToken.token_hash == token_hash, RefreshToken.user_id == user_id
                )
            )
            record = result.scalar_one_or_none()
            if record is not None:
                record.revoked_at = now
        else:
            result = await self.db.execute(
                select(RefreshToken).where(
                    RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
                )
            )
            for record in result.scalars().all():
                record.revoked_at = now

        await self.db.flush()

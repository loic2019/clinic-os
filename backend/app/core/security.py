"""
Security primitives: password hashing and JWT handling.

- Passwords are hashed with Argon2 (winner of the Password Hashing
  Competition, recommended over bcrypt for new systems).
- Access tokens are short-lived JWTs carrying the user id plus a
  snapshot of role/permission codes, so most requests can authorize
  without hitting the database.
- Refresh tokens are opaque random strings; only their SHA-256 hash is
  persisted (see app.models.refresh_token), so a leaked database dump
  does not expose usable tokens.
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    *,
    user_id: uuid.UUID,
    username: str,
    roles: list[str],
    permissions: list[str],
) -> str:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "username": username,
        "roles": roles,
        "permissions": permissions,
        "type": TOKEN_TYPE_ACCESS,
        "iat": now,
        "exp": expires_at,
        "jti": secrets.token_hex(16),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def generate_refresh_token_value() -> str:
    """Opaque, high-entropy token. Only its hash is ever stored."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def decode_access_token(token: str) -> dict[str, Any]:
    """Raises JWTError (or subclasses) if the token is invalid or expired."""
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    if payload.get("type") != TOKEN_TYPE_ACCESS:
        raise JWTError("Invalid token type")
    return payload


def refresh_token_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

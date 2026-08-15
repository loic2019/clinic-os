"""Pydantic schemas for /api/auth."""

import uuid

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, examples=["admin"])
    password: str = Field(..., min_length=1, examples=["ChangeMe123!"])


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = Field(
        default=None,
        description="If provided, only this session is revoked. Otherwise all of the current user's sessions are revoked.",
    )


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class CurrentUser(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    full_name: str
    roles: list[str]
    permissions: list[str]

    model_config = {"from_attributes": True}

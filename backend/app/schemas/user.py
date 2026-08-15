"""Pydantic schemas for /api/users."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)
    phone: str | None = None
    password: str = Field(..., min_length=8, max_length=128)
    role_names: list[str] = Field(default_factory=list, description="e.g. ['CASHIER']")

    @field_validator("password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        if value.isalpha() or value.isdigit():
            raise ValueError(
                "Password must mix letters and numbers (or symbols), not be a single character class."
            )
        return value


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = None
    is_active: bool | None = None
    role_names: list[str] | None = None


class UserRead(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    full_name: str
    phone: str | None
    is_active: bool
    roles: list[str]
    last_login_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("roles", mode="before")
    @classmethod
    def extract_role_names(cls, value):
        if value and hasattr(value[0], "name"):
            return [r.name for r in value]
        return value


class UserListResponse(BaseModel):
    items: list[UserRead]
    total: int
    page: int
    page_size: int

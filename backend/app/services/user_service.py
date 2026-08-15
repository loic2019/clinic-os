"""User management business logic, used by /api/users (admin-only)."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import hash_password
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, UserUpdate


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.users = UserRepository(db)

    async def list_users(self, *, page: int, page_size: int, search: str | None):
        return await self.users.list_paginated(page=page, page_size=page_size, search=search)

    async def get_user(self, user_id: uuid.UUID) -> User:
        user = await self.users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("Utilisateur introuvable.")
        return user

    async def create_user(self, payload: UserCreate) -> User:
        if await self.users.get_by_username(payload.username):
            raise ConflictError("Ce nom d'utilisateur est déjà utilisé.")
        if await self.users.get_by_email(payload.email):
            raise ConflictError("Cet email est déjà utilisé.")

        roles = await self.users.get_roles_by_names(payload.role_names)

        user = User(
            username=payload.username,
            email=payload.email,
            full_name=payload.full_name,
            phone=payload.phone,
            hashed_password=hash_password(payload.password),
            roles=roles,
        )
        return await self.users.create(user)

    async def update_user(self, user_id: uuid.UUID, payload: UserUpdate) -> User:
        user = await self.get_user(user_id)

        if payload.email is not None and payload.email != user.email:
            if await self.users.get_by_email(payload.email):
                raise ConflictError("Cet email est déjà utilisé.")
            user.email = payload.email

        if payload.full_name is not None:
            user.full_name = payload.full_name
        if payload.phone is not None:
            user.phone = payload.phone
        if payload.is_active is not None:
            user.is_active = payload.is_active
        if payload.role_names is not None:
            user.roles = await self.users.get_roles_by_names(payload.role_names)

        return await self.users.save(user)

    async def deactivate_user(self, user_id: uuid.UUID) -> User:
        user = await self.get_user(user_id)
        user.is_active = False
        return await self.users.save(user)

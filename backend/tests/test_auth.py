"""
Phase 2 integration tests: login, JWT, RBAC, refresh rotation, logout.

These tests hit a real database (whatever DATABASE_URL points to), the
same way the app does in production — no mocking of the DB layer.
Each test creates its own uniquely-named role/user data so the suite
can be re-run safely without manual cleanup.
"""

import uuid

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

import app.core.database as db_module
from app.core.security import hash_password
from app.main import app
from app.models.role import Permission, Role


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def unique_suffix():
    return uuid.uuid4().hex[:8]


async def _ensure_role_with_permission(role_name: str, permission_code: str, module: str):
    """Test helper: guarantees a role granting exactly one permission exists."""
    async with db_module.AsyncSessionLocal() as session:
        result = await session.execute(select(Role).where(Role.name == role_name))
        role = result.scalar_one_or_none()
        if role is None:
            role = Role(name=role_name, permissions=[])
            session.add(role)
            await session.flush()

        result = await session.execute(select(Permission).where(Permission.code == permission_code))
        permission = result.scalar_one_or_none()
        if permission is None:
            permission = Permission(code=permission_code, module=module, description="test permission")
            session.add(permission)
            await session.flush()

        existing_codes = {p.code for p in role.permissions}
        if permission_code not in existing_codes:
            role.permissions.append(permission)

        await session.commit()
        return role


async def _create_user(username: str, password: str, role_name: str):
    async with db_module.AsyncSessionLocal() as session:
        result = await session.execute(select(Role).where(Role.name == role_name))
        role = result.scalar_one()

        from app.models.user import User

        user = User(
            username=username,
            email=f"{username}@example.com",
            full_name=f"Test User {username}",
            hashed_password=hash_password(password),
            roles=[role],
        )
        session.add(user)
        await session.commit()
        return user


@pytest.mark.asyncio
async def test_login_rejects_wrong_password(client, unique_suffix):
    role_name = f"TEST_ROLE_{unique_suffix}"
    await _ensure_role_with_permission(role_name, f"testmod_{unique_suffix}.read", f"testmod_{unique_suffix}")
    username = f"user_{unique_suffix}"
    await _create_user(username, "CorrectPass1!", role_name)

    response = await client.post("/api/auth/login", json={"username": username, "password": "WrongPass!"})
    assert response.status_code == 401
    assert response.json()["success"] is False


@pytest.mark.asyncio
async def test_login_succeeds_and_returns_tokens(client, unique_suffix):
    role_name = f"TEST_ROLE_{unique_suffix}"
    await _ensure_role_with_permission(role_name, f"testmod_{unique_suffix}.read", f"testmod_{unique_suffix}")
    username = f"user_{unique_suffix}"
    await _create_user(username, "CorrectPass1!", role_name)

    response = await client.post("/api/auth/login", json={"username": username, "password": "CorrectPass1!"})
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "access_token" in body["data"]
    assert "refresh_token" in body["data"]


@pytest.mark.asyncio
async def test_me_returns_roles_and_permissions(client, unique_suffix):
    role_name = f"TEST_ROLE_{unique_suffix}"
    perm_code = f"testmod_{unique_suffix}.read"
    await _ensure_role_with_permission(role_name, perm_code, f"testmod_{unique_suffix}")
    username = f"user_{unique_suffix}"
    await _create_user(username, "CorrectPass1!", role_name)

    login = await client.post("/api/auth/login", json={"username": username, "password": "CorrectPass1!"})
    token = login.json()["data"]["access_token"]

    response = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert role_name in data["roles"]
    assert perm_code in data["permissions"]


@pytest.mark.asyncio
async def test_protected_route_requires_token(client):
    response = await client.get("/api/users")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_rbac_blocks_missing_permission(client, unique_suffix):
    # A role with an unrelated permission must NOT unlock /api/users (needs users.read).
    role_name = f"TEST_ROLE_{unique_suffix}"
    await _ensure_role_with_permission(role_name, f"testmod_{unique_suffix}.read", f"testmod_{unique_suffix}")
    username = f"user_{unique_suffix}"
    await _create_user(username, "CorrectPass1!", role_name)

    login = await client.post("/api/auth/login", json={"username": username, "password": "CorrectPass1!"})
    token = login.json()["data"]["access_token"]

    response = await client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_refresh_token_rotates_and_old_token_is_revoked(client, unique_suffix):
    role_name = f"TEST_ROLE_{unique_suffix}"
    await _ensure_role_with_permission(role_name, f"testmod_{unique_suffix}.read", f"testmod_{unique_suffix}")
    username = f"user_{unique_suffix}"
    await _create_user(username, "CorrectPass1!", role_name)

    login = await client.post("/api/auth/login", json={"username": username, "password": "CorrectPass1!"})
    refresh_token = login.json()["data"]["refresh_token"]

    first_refresh = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert first_refresh.status_code == 200

    second_refresh = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert second_refresh.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(client, unique_suffix):
    role_name = f"TEST_ROLE_{unique_suffix}"
    await _ensure_role_with_permission(role_name, f"testmod_{unique_suffix}.read", f"testmod_{unique_suffix}")
    username = f"user_{unique_suffix}"
    await _create_user(username, "CorrectPass1!", role_name)

    login = await client.post("/api/auth/login", json={"username": username, "password": "CorrectPass1!"})
    access_token = login.json()["data"]["access_token"]
    refresh_token = login.json()["data"]["refresh_token"]

    logout = await client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"refresh_token": refresh_token},
    )
    assert logout.status_code == 200

    reuse = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert reuse.status_code == 401

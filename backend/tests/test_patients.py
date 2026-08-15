"""
Phase 3 integration tests: patient CRUD, numbering, search, archive,
sub-resources, and RBAC — run against a real database (see
tests/conftest.py for the NullPool fix that makes this safe under
pytest-asyncio).
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


async def _login_as(client, username: str, password: str) -> str:
    response = await client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["data"]["access_token"]


async def _admin_token(client) -> str:
    """Relies on database/seed.py having been run (admin / ChangeMe123!)."""
    return await _login_as(client, "admin", "ChangeMe123!")


async def _create_role_without_patient_access(unique_suffix: str) -> str:
    role_name = f"TEST_NO_PATIENTS_{unique_suffix}"
    async with db_module.AsyncSessionLocal() as session:
        result = await session.execute(select(Role).where(Role.name == role_name))
        role = result.scalar_one_or_none()
        if role is None:
            role = Role(name=role_name, permissions=[])
            session.add(role)
            await session.flush()

        code = f"unrelated_{unique_suffix}.read"
        result = await session.execute(select(Permission).where(Permission.code == code))
        permission = result.scalar_one_or_none()
        if permission is None:
            permission = Permission(code=code, module=f"unrelated_{unique_suffix}", description="test")
            session.add(permission)
            await session.flush()

        if code not in {p.code for p in role.permissions}:
            role.permissions.append(permission)

        from app.models.user import User

        username = f"nopatients_{unique_suffix}"
        user = User(
            username=username,
            email=f"{username}@example.com",
            full_name="No Patients User",
            hashed_password=hash_password("TestPass123!"),
            roles=[role],
        )
        session.add(user)
        await session.commit()
    return username


@pytest.mark.asyncio
async def test_create_patient_generates_sequential_numbers(client, unique_suffix):
    token = await _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    r1 = await client.post(
        "/api/patients",
        headers=headers,
        json={"first_name": f"Test{unique_suffix}A", "last_name": "Patient"},
    )
    r2 = await client.post(
        "/api/patients",
        headers=headers,
        json={"first_name": f"Test{unique_suffix}B", "last_name": "Patient"},
    )
    assert r1.status_code == 200
    assert r2.status_code == 200

    n1 = r1.json()["data"]["patient_number"]
    n2 = r2.json()["data"]["patient_number"]
    assert n1.startswith("PAT-")
    assert n1 != n2
    # sequential: numeric suffix of n2 == numeric suffix of n1 + 1
    seq1 = int(n1.rsplit("-", 1)[1])
    seq2 = int(n2.rsplit("-", 1)[1])
    assert seq2 == seq1 + 1


@pytest.mark.asyncio
async def test_create_patient_with_nested_subresources(client, unique_suffix):
    token = await _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/api/patients",
        headers=headers,
        json={
            "first_name": f"Test{unique_suffix}",
            "last_name": "Nested",
            "contacts": [{"full_name": "Contact Person", "phone": "123"}],
            "insurances": [{"insurance_name": "TestInsurance", "is_primary": True}],
            "allergies": [{"allergen": "TestAllergen"}],
            "medical_histories": [{"condition": "TestCondition"}],
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data["contacts"]) == 1
    assert len(data["insurances"]) == 1
    assert len(data["allergies"]) == 1
    assert len(data["medical_histories"]) == 1


@pytest.mark.asyncio
async def test_search_finds_patient_by_name_and_number(client, unique_suffix):
    token = await _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    unique_last_name = f"Searchable{unique_suffix}"
    create = await client.post(
        "/api/patients",
        headers=headers,
        json={"first_name": "Find", "last_name": unique_last_name},
    )
    number = create.json()["data"]["patient_number"]

    by_name = await client.get("/api/patients", headers=headers, params={"search": unique_last_name})
    assert by_name.json()["data"]["total"] == 1

    by_number = await client.get("/api/patients", headers=headers, params={"search": number})
    assert by_number.json()["data"]["total"] == 1


@pytest.mark.asyncio
async def test_archive_excludes_from_default_list_but_not_from_include_archived(client, unique_suffix):
    token = await _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    unique_last_name = f"Archivable{unique_suffix}"
    create = await client.post(
        "/api/patients",
        headers=headers,
        json={"first_name": "Arch", "last_name": unique_last_name},
    )
    patient_id = create.json()["data"]["id"]

    archive = await client.post(f"/api/patients/{patient_id}/archive", headers=headers)
    assert archive.status_code == 200
    assert archive.json()["data"]["is_archived"] is True

    default_list = await client.get("/api/patients", headers=headers, params={"search": unique_last_name})
    assert default_list.json()["data"]["total"] == 0

    with_archived = await client.get(
        "/api/patients", headers=headers, params={"search": unique_last_name, "include_archived": True}
    )
    assert with_archived.json()["data"]["total"] == 1

    unarchive = await client.post(f"/api/patients/{patient_id}/unarchive", headers=headers)
    assert unarchive.json()["data"]["is_archived"] is False


@pytest.mark.asyncio
async def test_add_and_remove_allergy(client, unique_suffix):
    token = await _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    create = await client.post(
        "/api/patients",
        headers=headers,
        json={"first_name": "Allergy", "last_name": f"Test{unique_suffix}"},
    )
    patient_id = create.json()["data"]["id"]

    add = await client.post(
        f"/api/patients/{patient_id}/allergies", headers=headers, json={"allergen": "Latex"}
    )
    assert add.status_code == 200
    allergy_id = add.json()["data"]["id"]

    detail = await client.get(f"/api/patients/{patient_id}", headers=headers)
    assert len(detail.json()["data"]["allergies"]) == 1

    remove = await client.delete(f"/api/patients/{patient_id}/allergies/{allergy_id}", headers=headers)
    assert remove.status_code == 200

    detail2 = await client.get(f"/api/patients/{patient_id}", headers=headers)
    assert len(detail2.json()["data"]["allergies"]) == 0


@pytest.mark.asyncio
async def test_rbac_blocks_role_without_patients_permission(client, unique_suffix):
    username = await _create_role_without_patient_access(unique_suffix)
    token = await _login_as(client, username, "TestPass123!")

    response = await client.get("/api/patients", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_get_nonexistent_patient_returns_404(client):
    token = await _admin_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get(f"/api/patients/{uuid.uuid4()}", headers=headers)
    assert response.status_code == 404

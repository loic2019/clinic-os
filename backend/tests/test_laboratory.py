"""
Phase 5 integration tests: lab test catalog, order creation with
numbering, sample collection status transitions, automatic abnormal
flagging, validation workflow, and RBAC — run against a real database.
"""

import uuid

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def unique_suffix():
    return uuid.uuid4().hex[:8]


async def _admin_headers(client) -> dict:
    r = await client.post("/api/auth/login", json={"username": "admin", "password": "ChangeMe123!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


async def _create_patient(client, headers, suffix: str) -> str:
    r = await client.post(
        "/api/patients", headers=headers, json={"first_name": "LabTest", "last_name": f"P{suffix}"}
    )
    assert r.status_code == 200
    return r.json()["data"]["id"]


async def _create_lab_test(client, headers, suffix: str, low=10.0, high=20.0) -> str:
    r = await client.post(
        "/api/laboratory/tests",
        headers=headers,
        json={
            "code": f"TLAB-{suffix}",
            "name": f"Test Analyse {suffix}",
            "category": "Test",
            "unit": "unit",
            "reference_range_low": low,
            "reference_range_high": high,
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["id"]


@pytest.mark.asyncio
async def test_order_generates_sequential_lab_numbers(client, unique_suffix):
    headers = await _admin_headers(client)
    patient_id = await _create_patient(client, headers, unique_suffix)
    test_id = await _create_lab_test(client, headers, unique_suffix)

    r1 = await client.post(
        "/api/laboratory/orders", headers=headers, json={"patient_id": patient_id, "lab_test_ids": [test_id]}
    )
    r2 = await client.post(
        "/api/laboratory/orders", headers=headers, json={"patient_id": patient_id, "lab_test_ids": [test_id]}
    )
    assert r1.status_code == 200
    assert r2.status_code == 200

    n1 = r1.json()["data"]["order_number"]
    n2 = r2.json()["data"]["order_number"]
    assert n1.startswith("LAB-")
    seq1 = int(n1.rsplit("-", 1)[1])
    seq2 = int(n2.rsplit("-", 1)[1])
    assert seq2 == seq1 + 1


@pytest.mark.asyncio
async def test_sample_collection_transitions_statuses(client, unique_suffix):
    headers = await _admin_headers(client)
    patient_id = await _create_patient(client, headers, unique_suffix)
    test_id = await _create_lab_test(client, headers, unique_suffix)

    order = await client.post(
        "/api/laboratory/orders", headers=headers, json={"patient_id": patient_id, "lab_test_ids": [test_id]}
    )
    order_id = order.json()["data"]["id"]
    assert order.json()["data"]["status"] == "ORDERED"
    assert order.json()["data"]["items"][0]["status"] == "PENDING"

    sample = await client.post(
        f"/api/laboratory/orders/{order_id}/samples", headers=headers, json={"sample_type": "BLOOD"}
    )
    assert sample.status_code == 200
    assert sample.json()["data"]["status"] == "IN_PROGRESS"
    assert sample.json()["data"]["items"][0]["status"] == "SAMPLE_COLLECTED"


@pytest.mark.asyncio
async def test_result_entry_flags_abnormal_values_correctly(client, unique_suffix):
    headers = await _admin_headers(client)
    patient_id = await _create_patient(client, headers, unique_suffix)
    test_id = await _create_lab_test(client, headers, unique_suffix, low=10.0, high=20.0)

    order = await client.post(
        "/api/laboratory/orders", headers=headers, json={"patient_id": patient_id, "lab_test_ids": [test_id]}
    )
    order_id = order.json()["data"]["id"]
    item_id = order.json()["data"]["items"][0]["id"]

    # Below range -> abnormal
    r = await client.post(
        f"/api/laboratory/orders/{order_id}/items/{item_id}/result", headers=headers, json={"value_numeric": 5.0}
    )
    assert r.status_code == 200
    item = r.json()["data"]["items"][0]
    assert item["status"] == "RESULT_ENTERED"
    assert item["result"]["is_abnormal"] is True

    # Within range -> not abnormal (re-entering before validation is allowed)
    r = await client.post(
        f"/api/laboratory/orders/{order_id}/items/{item_id}/result", headers=headers, json={"value_numeric": 15.0}
    )
    assert r.json()["data"]["items"][0]["result"]["is_abnormal"] is False


@pytest.mark.asyncio
async def test_validation_workflow_completes_order_and_locks_result(client, unique_suffix):
    headers = await _admin_headers(client)
    patient_id = await _create_patient(client, headers, unique_suffix)
    test_id = await _create_lab_test(client, headers, unique_suffix)

    order = await client.post(
        "/api/laboratory/orders", headers=headers, json={"patient_id": patient_id, "lab_test_ids": [test_id]}
    )
    order_id = order.json()["data"]["id"]
    item_id = order.json()["data"]["items"][0]["id"]

    await client.post(
        f"/api/laboratory/orders/{order_id}/items/{item_id}/result", headers=headers, json={"value_numeric": 15.0}
    )

    validate = await client.post(f"/api/laboratory/orders/{order_id}/items/{item_id}/validate", headers=headers)
    assert validate.status_code == 200
    assert validate.json()["data"]["status"] == "COMPLETED"
    assert validate.json()["data"]["items"][0]["status"] == "VALIDATED"

    # Locked: cannot re-enter a result on a validated item
    relock = await client.post(
        f"/api/laboratory/orders/{order_id}/items/{item_id}/result", headers=headers, json={"value_numeric": 99}
    )
    assert relock.status_code == 409


@pytest.mark.asyncio
async def test_validate_without_result_is_rejected(client, unique_suffix):
    headers = await _admin_headers(client)
    patient_id = await _create_patient(client, headers, unique_suffix)
    test_id = await _create_lab_test(client, headers, unique_suffix)

    order = await client.post(
        "/api/laboratory/orders", headers=headers, json={"patient_id": patient_id, "lab_test_ids": [test_id]}
    )
    order_id = order.json()["data"]["id"]
    item_id = order.json()["data"]["items"][0]["id"]

    r = await client.post(f"/api/laboratory/orders/{order_id}/items/{item_id}/validate", headers=headers)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "NO_RESULT"


@pytest.mark.asyncio
async def test_duplicate_lab_test_code_rejected(client, unique_suffix):
    headers = await _admin_headers(client)
    await _create_lab_test(client, headers, unique_suffix)

    r = await client.post(
        "/api/laboratory/tests",
        headers=headers,
        json={"code": f"TLAB-{unique_suffix}", "name": "Dup", "category": "Test"},
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_rbac_pharmacist_blocked_from_laboratory(client, unique_suffix):
    headers = await _admin_headers(client)

    r = await client.post(
        "/api/users",
        headers=headers,
        json={
            "username": f"pharma_{unique_suffix}",
            "email": f"pharma_{unique_suffix}@example.com",
            "full_name": "Test Pharmacist",
            "password": "PharmaPass1!",
            "role_names": ["PHARMACIST"],
        },
    )
    assert r.status_code == 200

    login = await client.post(
        "/api/auth/login", json={"username": f"pharma_{unique_suffix}", "password": "PharmaPass1!"}
    )
    token = login.json()["data"]["access_token"]

    response = await client.get("/api/laboratory/orders", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403

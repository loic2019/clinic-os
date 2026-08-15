"""
Phase 4 integration tests: doctors, medical act catalog + price history,
consultations (vitals, linked acts with price snapshot, prescriptions),
and appointments (conflict detection, cancellation) — run against a
real database.
"""

import uuid
from datetime import datetime, timedelta, timezone

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
        "/api/patients", headers=headers, json={"first_name": "Test", "last_name": f"P{suffix}"}
    )
    assert r.status_code == 200
    return r.json()["data"]["id"]


async def _create_doctor(client, headers, suffix: str) -> str:
    r = await client.post(
        "/api/doctors",
        headers=headers,
        json={"first_name": "Test", "last_name": f"Doc{suffix}", "specialty": "Généraliste"},
    )
    assert r.status_code == 200
    return r.json()["data"]["id"]


async def _create_medical_act(client, headers, suffix: str, price: float = 5000) -> str:
    r = await client.post(
        "/api/medical-acts",
        headers=headers,
        json={
            "code": f"TEST-{suffix}",
            "name": f"Test Act {suffix}",
            "category": "Test",
            "initial_price": price,
        },
    )
    assert r.status_code == 200
    return r.json()["data"]["id"]


# --- Doctors -----------------------------------------------------------


@pytest.mark.asyncio
async def test_create_and_list_doctor(client, unique_suffix):
    headers = await _admin_headers(client)
    doctor_id = await _create_doctor(client, headers, unique_suffix)

    r = await client.get("/api/doctors", headers=headers, params={"search": f"Doc{unique_suffix}"})
    assert r.status_code == 200
    assert r.json()["data"]["total"] == 1
    assert r.json()["data"]["items"][0]["id"] == doctor_id


# --- Medical acts catalog ------------------------------------------------


@pytest.mark.asyncio
async def test_medical_act_price_history_never_overwritten(client, unique_suffix):
    headers = await _admin_headers(client)
    act_id = await _create_medical_act(client, headers, unique_suffix, price=10000)

    r = await client.get(f"/api/medical-acts/{act_id}", headers=headers)
    assert r.json()["data"]["current_price"] == 10000.0
    assert len(r.json()["data"]["price_history"]) == 1

    # Add a price effective in the future -> current_price must NOT change yet
    future_date = (datetime.now(timezone.utc) + timedelta(days=30)).date().isoformat()
    r = await client.post(
        f"/api/medical-acts/{act_id}/prices",
        headers=headers,
        json={"price": 15000, "effective_from": future_date},
    )
    assert r.status_code == 200
    assert r.json()["data"]["current_price"] == 10000.0  # unchanged, future price not yet active
    assert len(r.json()["data"]["price_history"]) == 2  # but history keeps both


@pytest.mark.asyncio
async def test_duplicate_medical_act_code_rejected(client, unique_suffix):
    headers = await _admin_headers(client)
    await _create_medical_act(client, headers, unique_suffix)

    r = await client.post(
        "/api/medical-acts",
        headers=headers,
        json={
            "code": f"TEST-{unique_suffix}",
            "name": "Duplicate",
            "category": "Test",
            "initial_price": 1000,
        },
    )
    assert r.status_code == 409


# --- Consultations -------------------------------------------------------


@pytest.mark.asyncio
async def test_consultation_generates_sequential_numbers_and_computes_bmi(client, unique_suffix):
    headers = await _admin_headers(client)
    patient_id = await _create_patient(client, headers, unique_suffix)

    r1 = await client.post(
        "/api/consultations",
        headers=headers,
        json={"patient_id": patient_id, "weight_kg": 80, "height_cm": 200},
    )
    r2 = await client.post(
        "/api/consultations",
        headers=headers,
        json={"patient_id": patient_id},
    )
    assert r1.status_code == 200
    assert r2.status_code == 200

    n1 = r1.json()["data"]["consultation_number"]
    n2 = r2.json()["data"]["consultation_number"]
    assert n1.startswith("CONS-")
    seq1 = int(n1.rsplit("-", 1)[1])
    seq2 = int(n2.rsplit("-", 1)[1])
    assert seq2 == seq1 + 1

    assert r1.json()["data"]["bmi"] == 20.0  # 80 / 2.0^2


@pytest.mark.asyncio
async def test_consultation_snapshots_act_price(client, unique_suffix):
    headers = await _admin_headers(client)
    patient_id = await _create_patient(client, headers, unique_suffix)
    act_id = await _create_medical_act(client, headers, unique_suffix, price=7000)

    consult = await client.post(
        "/api/consultations",
        headers=headers,
        json={"patient_id": patient_id, "acts": [{"medical_act_id": act_id, "quantity": 2}]},
    )
    assert consult.status_code == 200
    act_line = consult.json()["data"]["acts"][0]
    assert act_line["unit_price_applied"] == 7000.0
    assert act_line["quantity"] == 2

    # Now change the catalog price — the already-created consultation line must NOT change.
    await client.post(f"/api/medical-acts/{act_id}/prices", headers=headers, json={"price": 9000})

    detail = await client.get(f"/api/consultations/{consult.json()['data']['id']}", headers=headers)
    assert detail.json()["data"]["acts"][0]["unit_price_applied"] == 7000.0


@pytest.mark.asyncio
async def test_consultation_with_prescription(client, unique_suffix):
    headers = await _admin_headers(client)
    patient_id = await _create_patient(client, headers, unique_suffix)

    r = await client.post(
        "/api/consultations",
        headers=headers,
        json={
            "patient_id": patient_id,
            "diagnosis": "Test diagnosis",
            "prescriptions": [
                {
                    "items": [
                        {"medication_name": "TestMed", "dosage": "10mg", "frequency": "2x/jour"}
                    ]
                }
            ],
        },
    )
    assert r.status_code == 200
    prescriptions = r.json()["data"]["prescriptions"]
    assert len(prescriptions) == 1
    assert prescriptions[0]["items"][0]["medication_name"] == "TestMed"


# --- Appointments ----------------------------------------------------------


@pytest.mark.asyncio
async def test_appointment_conflict_detection_and_cancellation_frees_slot(client, unique_suffix):
    headers = await _admin_headers(client)
    patient_id = await _create_patient(client, headers, unique_suffix)
    doctor_id = await _create_doctor(client, headers, unique_suffix)

    scheduled = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()

    first = await client.post(
        "/api/appointments",
        headers=headers,
        json={"patient_id": patient_id, "doctor_id": doctor_id, "scheduled_at": scheduled, "duration_minutes": 30},
    )
    assert first.status_code == 200

    conflict = await client.post(
        "/api/appointments",
        headers=headers,
        json={"patient_id": patient_id, "doctor_id": doctor_id, "scheduled_at": scheduled, "duration_minutes": 30},
    )
    assert conflict.status_code == 409

    cancel = await client.post(f"/api/appointments/{first.json()['data']['id']}/cancel", headers=headers)
    assert cancel.status_code == 200
    assert cancel.json()["data"]["status"] == "CANCELLED"

    now_free = await client.post(
        "/api/appointments",
        headers=headers,
        json={"patient_id": patient_id, "doctor_id": doctor_id, "scheduled_at": scheduled, "duration_minutes": 30},
    )
    assert now_free.status_code == 200


@pytest.mark.asyncio
async def test_rbac_pharmacist_blocked_from_appointments(client, unique_suffix):
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
    pharma_token = login.json()["data"]["access_token"]

    response = await client.get("/api/appointments", headers={"Authorization": f"Bearer {pharma_token}"})
    assert response.status_code == 403

"""
Phase 7-8 integration tests: invoice creation with server-side price
calculation, partial/full payment status transitions, overpayment
protection, cash session open/close with discrepancy detection,
cancellation workflow, and RBAC — run against a real database.
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


async def _create_cashier_headers(client, admin_headers, suffix: str) -> dict:
    r = await client.post(
        "/api/users",
        headers=admin_headers,
        json={
            "username": f"cashier_{suffix}",
            "email": f"cashier_{suffix}@example.com",
            "full_name": "Test Cashier",
            "password": "CashierPass1!",
            "role_names": ["CASHIER"],
        },
    )
    assert r.status_code == 200, r.text
    login = await client.post(
        "/api/auth/login", json={"username": f"cashier_{suffix}", "password": "CashierPass1!"}
    )
    return {"Authorization": f"Bearer {login.json()['data']['access_token']}"}


async def _create_patient(client, headers, suffix: str) -> str:
    r = await client.post(
        "/api/patients", headers=headers, json={"first_name": "Bill", "last_name": f"P{suffix}"}
    )
    assert r.status_code == 200
    return r.json()["data"]["id"]


async def _open_session_on_any_free_register(client, cashier_headers) -> tuple[str, str]:
    """Returns (register_id, session_id), trying registers until one is free."""
    r = await client.get("/api/cash/registers", headers=cashier_headers)
    for reg in r.json()["data"]:
        resp = await client.post(
            "/api/cash/sessions/open",
            headers=cashier_headers,
            json={"cash_register_id": reg["id"], "opening_balance": 100000},
        )
        if resp.status_code == 200:
            return reg["id"], resp.json()["data"]["id"]
    raise AssertionError("No free cash register available for test")


@pytest.mark.asyncio
async def test_invoice_calculates_total_server_side_from_catalog(client, unique_suffix):
    headers = await _admin_headers(client)
    patient_id = await _create_patient(client, headers, unique_suffix)

    acts = await client.get("/api/medical-acts", headers=headers, params={"search": "CONS-001"})
    act = acts.json()["data"]["items"][0]

    r = await client.post(
        "/api/invoices",
        headers=headers,
        json={
            "patient_id": patient_id,
            "items": [
                {"item_type": "MEDICAL_ACT", "medical_act_id": act["id"], "quantity": 2},
                {"item_type": "OTHER", "description": "Frais", "unit_price": 500, "quantity": 1},
            ],
        },
    )
    assert r.status_code == 200, r.text
    invoice = r.json()["data"]
    assert invoice["invoice_number"].startswith("FAC-")
    expected_total = act["current_price"] * 2 + 500
    assert invoice["total"] == expected_total
    assert invoice["status"] == "UNPAID"


@pytest.mark.asyncio
async def test_invoice_rejects_free_line_without_price(client, unique_suffix):
    headers = await _admin_headers(client)
    patient_id = await _create_patient(client, headers, unique_suffix)

    r = await client.post(
        "/api/invoices",
        headers=headers,
        json={
            "patient_id": patient_id,
            "items": [{"item_type": "OTHER", "description": "Sans prix"}],
        },
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_ITEM"


@pytest.mark.asyncio
async def test_partial_then_full_payment_transitions_status(client, unique_suffix):
    headers = await _admin_headers(client)
    patient_id = await _create_patient(client, headers, unique_suffix)

    r = await client.post(
        "/api/invoices",
        headers=headers,
        json={"patient_id": patient_id, "items": [{"item_type": "OTHER", "description": "Test", "unit_price": 10000, "quantity": 1}]},
    )
    invoice_id = r.json()["data"]["id"]

    r = await client.post(
        "/api/payments", headers=headers, json={"invoice_id": invoice_id, "method": "CASH", "amount": 4000}
    )
    assert r.status_code == 200

    detail = await client.get(f"/api/invoices/{invoice_id}", headers=headers)
    assert detail.json()["data"]["status"] == "PARTIALLY_PAID"
    assert detail.json()["data"]["balance_due"] == 6000

    r = await client.post(
        "/api/payments", headers=headers, json={"invoice_id": invoice_id, "method": "MOBILE_MONEY_MTN", "amount": 6000}
    )
    assert r.status_code == 200

    detail = await client.get(f"/api/invoices/{invoice_id}", headers=headers)
    assert detail.json()["data"]["status"] == "PAID"
    assert detail.json()["data"]["balance_due"] == 0


@pytest.mark.asyncio
async def test_payment_cannot_exceed_balance_due(client, unique_suffix):
    headers = await _admin_headers(client)
    patient_id = await _create_patient(client, headers, unique_suffix)

    r = await client.post(
        "/api/invoices",
        headers=headers,
        json={"patient_id": patient_id, "items": [{"item_type": "OTHER", "description": "Test", "unit_price": 5000, "quantity": 1}]},
    )
    invoice_id = r.json()["data"]["id"]

    r = await client.post(
        "/api/payments", headers=headers, json={"invoice_id": invoice_id, "method": "CASH", "amount": 999999}
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_cash_session_open_close_with_no_discrepancy(client, unique_suffix):
    headers = await _create_cashier_headers(client, await _admin_headers(client), unique_suffix)

    register_id, session_id = await _open_session_on_any_free_register(client, headers)

    # Cannot open a second session as the same user
    r = await client.post(
        "/api/cash/sessions/open",
        headers=headers,
        json={"cash_register_id": register_id, "opening_balance": 1000},
    )
    assert r.status_code == 409

    close = await client.post(
        f"/api/cash/sessions/{session_id}/close", headers=headers, json={"closing_balance": 100000}
    )
    assert close.status_code == 200
    assert close.json()["data"]["difference"] == 0
    assert close.json()["data"]["status"] == "CLOSED"


@pytest.mark.asyncio
async def test_cash_session_close_requires_justification_on_discrepancy(client, unique_suffix):
    headers = await _create_cashier_headers(client, await _admin_headers(client), unique_suffix)
    _, session_id = await _open_session_on_any_free_register(client, headers)

    without_justification = await client.post(
        f"/api/cash/sessions/{session_id}/close", headers=headers, json={"closing_balance": 50000}
    )
    assert without_justification.status_code == 400
    assert without_justification.json()["error"]["code"] == "CASH_DISCREPANCY"

    with_justification = await client.post(
        f"/api/cash/sessions/{session_id}/close",
        headers=headers,
        json={"closing_balance": 50000, "difference_justification": "Erreur de comptage initiale"},
    )
    assert with_justification.status_code == 200
    assert with_justification.json()["data"]["difference"] == -50000


@pytest.mark.asyncio
async def test_cancellation_workflow_requires_admin_approval(client, unique_suffix):
    admin_headers = await _admin_headers(client)
    cashier_headers = await _create_cashier_headers(client, admin_headers, unique_suffix)
    patient_id = await _create_patient(client, admin_headers, unique_suffix)

    r = await client.post(
        "/api/invoices",
        headers=cashier_headers,
        json={"patient_id": patient_id, "items": [{"item_type": "OTHER", "description": "Erreur", "unit_price": 1000, "quantity": 1}]},
    )
    invoice_id = r.json()["data"]["id"]

    request = await client.post(
        f"/api/invoices/{invoice_id}/cancellation-requests",
        headers=cashier_headers,
        json={"reason": "Erreur de saisie"},
    )
    assert request.status_code == 200
    request_id = request.json()["data"]["id"]

    # Invoice must still be UNPAID/unaffected until admin approves
    detail = await client.get(f"/api/invoices/{invoice_id}", headers=admin_headers)
    assert detail.json()["data"]["status"] == "UNPAID"

    review = await client.post(
        f"/api/invoices/cancellation-requests/{request_id}/review",
        headers=admin_headers,
        json={"approve": True},
    )
    assert review.status_code == 200
    assert review.json()["data"]["status"] == "APPROVED"

    detail = await client.get(f"/api/invoices/{invoice_id}", headers=admin_headers)
    assert detail.json()["data"]["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_rbac_nurse_blocked_from_invoices(client, unique_suffix):
    admin_headers = await _admin_headers(client)

    r = await client.post(
        "/api/users",
        headers=admin_headers,
        json={
            "username": f"nurse_{unique_suffix}",
            "email": f"nurse_{unique_suffix}@example.com",
            "full_name": "Test Nurse",
            "password": "NursePass1!",
            "role_names": ["NURSE"],
        },
    )
    assert r.status_code == 200

    login = await client.post(
        "/api/auth/login", json={"username": f"nurse_{unique_suffix}", "password": "NursePass1!"}
    )
    token = login.json()["data"]["access_token"]

    response = await client.get("/api/invoices", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403

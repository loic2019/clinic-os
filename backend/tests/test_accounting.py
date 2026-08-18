"""
Phase 9 integration tests: chart of accounts, automatic
balanced-entry creation from payments and refunds, manual expense
logging, and the revenue/expense summary report — run against a real
database.
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
        "/api/patients", headers=headers, json={"first_name": "Acct", "last_name": f"P{suffix}"}
    )
    assert r.status_code == 200
    return r.json()["data"]["id"]


async def _create_paid_invoice(client, headers, patient_id: str, amount: float) -> tuple[str, str]:
    """Returns (invoice_id, payment_id)."""
    invoice = await client.post(
        "/api/invoices",
        headers=headers,
        json={"patient_id": patient_id, "items": [{"item_type": "OTHER", "description": "Test", "unit_price": amount, "quantity": 1}]},
    )
    invoice_id = invoice.json()["data"]["id"]
    payment = await client.post(
        "/api/payments", headers=headers, json={"invoice_id": invoice_id, "method": "CASH", "amount": amount}
    )
    return invoice_id, payment.json()["data"]["id"]


@pytest.mark.asyncio
async def test_chart_of_accounts_is_seeded(client):
    headers = await _admin_headers(client)
    r = await client.get("/api/accounting/accounts", headers=headers)
    assert r.status_code == 200
    codes = {a["code"] for a in r.json()["data"]}
    assert {"512", "706", "606"}.issubset(codes)


@pytest.mark.asyncio
async def test_payment_generates_balanced_accounting_entry(client, unique_suffix):
    headers = await _admin_headers(client)
    patient_id = await _create_patient(client, headers, unique_suffix)

    _, _ = await _create_paid_invoice(client, headers, patient_id, 12345)

    r = await client.get("/api/accounting/entries", headers=headers, params={"page_size": 1})
    latest = r.json()["data"]["items"][0]
    assert latest["source_type"] == "PAYMENT"
    assert latest["total_debit"] == latest["total_credit"] == 12345
    assert latest["entry_number"].startswith("ECR-")


@pytest.mark.asyncio
async def test_expense_generates_balanced_accounting_entry(client, unique_suffix):
    headers = await _admin_headers(client)

    r = await client.post(
        "/api/accounting/expenses",
        headers=headers,
        json={"category": "Test", "description": f"Depense {unique_suffix}", "amount": 7777},
    )
    assert r.status_code == 200
    expense = r.json()["data"]
    assert expense["expense_number"].startswith("DEP-")

    r = await client.get("/api/accounting/entries", headers=headers, params={"page_size": 1})
    latest = r.json()["data"]["items"][0]
    assert latest["source_type"] == "EXPENSE"
    assert latest["total_debit"] == latest["total_credit"] == 7777


@pytest.mark.asyncio
async def test_refund_reverses_the_original_entry(client, unique_suffix):
    headers = await _admin_headers(client)
    patient_id = await _create_patient(client, headers, unique_suffix)

    _, payment_id = await _create_paid_invoice(client, headers, patient_id, 8000)

    refund_req = await client.post(
        f"/api/payments/{payment_id}/refund-requests",
        headers=headers,
        json={"amount": 8000, "reason": "Test refund"},
    )
    request_id = refund_req.json()["data"]["id"]

    review = await client.post(
        f"/api/payments/refund-requests/{request_id}/review", headers=headers, json={"approve": True}
    )
    assert review.status_code == 200
    assert review.json()["data"]["status"] == "APPROVED"

    r = await client.get("/api/accounting/entries", headers=headers, params={"page_size": 1})
    latest = r.json()["data"]["items"][0]
    assert latest["source_type"] == "REFUND"
    assert latest["total_debit"] == latest["total_credit"] == 8000


@pytest.mark.asyncio
async def test_summary_reflects_revenue_and_expense(client, unique_suffix):
    headers = await _admin_headers(client)
    patient_id = await _create_patient(client, headers, unique_suffix)

    await _create_paid_invoice(client, headers, patient_id, 50000)
    await client.post(
        "/api/accounting/expenses",
        headers=headers,
        json={"category": "Test", "description": f"Dep {unique_suffix}", "amount": 10000},
    )

    r = await client.get("/api/accounting/summary", headers=headers)
    assert r.status_code == 200
    summary = r.json()["data"]
    assert summary["total_revenue"] >= 50000
    assert summary["total_expense"] >= 10000
    assert summary["net_result"] == round(summary["total_revenue"] - summary["total_expense"], 2)


@pytest.mark.asyncio
async def test_rbac_cashier_blocked_from_accounting(client, unique_suffix):
    admin_headers = await _admin_headers(client)

    r = await client.post(
        "/api/users",
        headers=admin_headers,
        json={
            "username": f"cash_{unique_suffix}",
            "email": f"cash_{unique_suffix}@example.com",
            "full_name": "Test Cashier",
            "password": "CashierPass1!",
            "role_names": ["CASHIER"],
        },
    )
    assert r.status_code == 200

    login = await client.post(
        "/api/auth/login", json={"username": f"cash_{unique_suffix}", "password": "CashierPass1!"}
    )
    token = login.json()["data"]["access_token"]

    response = await client.get("/api/accounting/summary", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403

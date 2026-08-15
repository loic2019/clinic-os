"""
Smoke test for the Phase 1 foundation.

Note: this test hits the app directly via ASGI transport, so no real
network/server is needed — but a reachable PostgreSQL is still required
for `database` to report "connected" (the endpoint itself still returns
200 even if the DB is unreachable, with status "degraded").
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "status" in body["data"]


@pytest.mark.asyncio
async def test_root_serves_frontend():
    """
    "/" now serves the frontend's index.html directly (same-origin
    deployment, see app/main.py) rather than a JSON welcome message —
    this is what makes CORS unnecessary in production.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "CLINIC OS" in response.text

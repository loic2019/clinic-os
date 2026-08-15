"""
GET /api/health

Simple liveness/readiness endpoint. Confirms the API is running and
checks connectivity to PostgreSQL. Used by Docker healthchecks,
monitoring, and the installation guide's first smoke test.
"""

from fastapi import APIRouter

from app.core.config import settings
from app.core.database import check_database_connection

router = APIRouter()


@router.get("/health")
async def health_check():
    db_ok = await check_database_connection()

    return {
        "success": True,
        "data": {
            "status": "ok" if db_ok else "degraded",
            "app": settings.APP_NAME,
            "environment": settings.ENVIRONMENT,
            "database": "connected" if db_ok else "unreachable",
        },
        "message": "CLINIC OS API is running.",
    }

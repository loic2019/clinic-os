"""
CLINIC OS — FastAPI application entrypoint.

Run locally with:
    uvicorn app.main:app --reload

Interactive docs are available at:
    /docs   (Swagger UI)
    /redoc  (ReDoc)
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s (%s environment)", settings.APP_NAME, settings.ENVIRONMENT)
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    description="Intelligent Clinical Management System — Backend API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Exception handling (standard success/error envelope) ---
register_exception_handlers(app)

# --- Routes ---
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


# --- Frontend static files ---
# Serves the HTML/CSS/JS frontend from the SAME origin as the API at
# the root path, so there is no cross-origin request involved and CORS
# is a non-issue — important for one-click deployments (e.g. Render)
# where the frontend and backend are one service with one URL. This
# mount is registered AFTER /docs, /redoc, /openapi.json, and /api/*,
# so those keep working — Starlette matches routes in registration
# order, and the more specific routes above win before the catch-all
# static mount is ever consulted. Works in two layouts:
#   - Local dev:      backend/app/main.py -> ../../frontend (repo layout)
#   - Docker/deploy:  frontend/ copied to /app/frontend alongside the app
# If no frontend directory is found, the API still runs fine on its own
# (e.g. a minimal API-only deployment) — "/" then simply 404s.
_FRONTEND_CANDIDATES = [
    Path(__file__).resolve().parent.parent.parent / "frontend",
    Path("/app/frontend"),
]
_frontend_dir = next((p for p in _FRONTEND_CANDIDATES if p.is_dir()), None)
if _frontend_dir is not None:
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
    logger.info("Serving frontend static files from %s", _frontend_dir)

# CLINIC OS — Backend API image (Phase 1)

FROM python:3.12-slim

# System deps for psycopg2 / asyncpg build
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

# database/seed.py lives outside backend/ in the repo but needs to run
# inside the container too (via `docker compose exec clinic-api python
# database/seed.py`, or Render's pre-deploy command) — copy it in
# alongside the app.
COPY database/ ./database/

# The frontend is served by the app itself (see app/main.py) so a
# single deployed service handles both — no separate frontend
# container/URL needed for platforms like Render.
COPY frontend/ ./frontend/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/api/health || exit 1

# Shell form (not exec/JSON form) so $PORT is substituted — hosting
# platforms like Render assign a dynamic port via this env var; falls
# back to 8000 for local `docker run` / docker-compose.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}

#!/bin/sh
# CLINIC OS — container startup script.
#
# Used as the Docker image's default command, for both local
# docker-compose and hosting platforms like Render. Keeping this logic
# in a real script file (instead of an inline shell one-liner inside
# docker-compose.yml / render.yaml) avoids fragile quote-escaping
# across different YAML/CLI parsers — each of which tokenizes strings
# slightly differently and silently breaks compound "a && b && c"
# commands in incompatible ways.
#
# Safe to run on every container start: both alembic upgrade and
# seed.py are idempotent.

set -e

echo "CLINIC OS: applying database migrations..."
alembic upgrade head

echo "CLINIC OS: seeding baseline data (roles, permissions, admin, demo data)..."
python database/seed.py

echo "CLINIC OS: starting server on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"

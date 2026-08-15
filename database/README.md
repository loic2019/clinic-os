# Database

CLINIC OS uses **PostgreSQL** as its single source of truth.

- Schema migrations are managed with **Alembic**, configured in
  `backend/alembic/` and `backend/alembic.ini`.
- `seed.py` populates demo data once domain models exist (Phase 3+).

## Common commands (run from `backend/`)

```bash
# Create a new migration from model changes
alembic revision --autogenerate -m "describe the change"

# Apply all pending migrations
alembic upgrade head

# Roll back one migration
alembic downgrade -1
```

No table is created manually — every schema change must go through an
Alembic migration so it is versioned and reproducible across
environments.

# CLINIC OS — Intelligent Clinical Management System

**Status: PHASE 4 — MÉDICAL** ✅ (Phases 1-3 also included)

This repository is being built phase by phase, as specified in the
project brief.

- **Phase 1 (Foundation):** architecture, tooling, `/api/health`.
- **Phase 2 (Authentication):** users, roles, permissions (RBAC), JWT
  login/refresh/logout, and backend-side permission enforcement on
  every protected route.
- **Phase 3 (Patients):** patient records, contacts, insurance,
  allergies, medical history, atomic auto-numbering (`PAT-2026-000001`),
  search, pagination, and archiving (never a hard delete).
- **Phase 4 (Médical):** doctors, medical act catalog with a
  never-overwritten price history, consultations (vitals, diagnosis,
  price-snapshotted acts, prescriptions), and appointments with
  doctor-schedule conflict detection.

No other business modules (billing, cash, pharmacy, etc.) exist yet —
those arrive from Phase 5 onward.

---

## 1. What Phase 4 adds

```text
backend/app/
├── models/
│   ├── doctor.py              Doctor (optionally linked to a login account)
│   ├── medical_act.py          MedicalAct + MedicalActPrice (history)
│   ├── consultation.py         Consultation, ConsultationAct, Prescription,
│   │                            PrescriptionItem
│   └── appointment.py          Appointment + AppointmentStatus
├── schemas/
│   ├── doctor.py, medical_act.py, consultation.py, appointment.py
├── repositories/
│   ├── doctor_repository.py, medical_act_repository.py,
│   │   consultation_repository.py, appointment_repository.py
├── services/
│   ├── doctor_service.py
│   ├── medical_act_service.py     catalog CRUD + price history rules
│   ├── consultation_service.py     vitals + price-snapshotted acts + prescriptions
│   └── appointment_service.py      creation with doctor conflict detection
└── api/routes/
    ├── doctors.py, medical_acts.py, consultations.py, appointments.py

backend/alembic/versions/     Migration creating doctors, medical_acts,
                                medical_act_prices, consultations,
                                consultation_acts, prescriptions,
                                prescription_items, appointments.

database/seed.py               Also seeds 10 catalog acts (spec section 13
                                examples: CONS-001/002, ACT-001..004,
                                LAB-001/002, IMG-001/002) and one demo
                                doctor, plus 10 new permissions
                                (doctors.*, medical_acts.*, appointments.*)
                                granted per role.
```

### Price history that is never overwritten (spec section 14)

`MedicalAct.current_price` is computed from `MedicalActPrice` rows —
never a single mutable column. Adding a new price via
`POST /api/medical-acts/{id}/prices` always **inserts** a new dated
row; nothing is ever updated in place. When a consultation links an
act, the price actually charged is copied onto the `ConsultationAct`
row at that moment (`unit_price_applied`) — verified end-to-end: raising
a catalog price afterwards does not change what an already-created
consultation shows.

### Appointment conflict detection (spec section 41)

Creating or rescheduling an appointment checks for time overlap against
the same doctor's other non-cancelled appointments and returns `409
CONFLICT` if the slot is taken. Cancelling an appointment immediately
frees the slot for a new booking — verified end-to-end.

### Endpoints

```text
GET/POST      /api/doctors
GET/PUT/DELETE /api/doctors/{id}                (DELETE = deactivate)

GET/POST      /api/medical-acts
GET/PUT/DELETE /api/medical-acts/{id}            (DELETE = deactivate)
POST          /api/medical-acts/{id}/prices       add a price (never overwrites)

GET/POST      /api/consultations
GET/PUT       /api/consultations/{id}

GET/POST      /api/appointments
GET/PUT       /api/appointments/{id}
POST          /api/appointments/{id}/cancel
```

---

## 2. File roles (Phases 1-3 recap)

| File | Role |
|---|---|
| `backend/app/main.py` | Creates the FastAPI app, wires CORS, exception handlers, and routes. |
| `backend/app/core/config.py` | Single source of truth for all settings, read from `.env`. |
| `backend/app/core/database.py` | Async PostgreSQL engine, session factory, `get_db()` dependency, connection healthcheck. |
| `backend/app/core/security.py` | Password hashing (Argon2) and JWT creation/verification. |
| `backend/app/core/exceptions.py` | Custom exceptions + handlers returning the `{success, data/error, message}` envelope used by every endpoint. |
| `backend/app/api/routes/health.py` | `GET /api/health` — confirms the API and the database are reachable. |
| `backend/app/api/routes/auth.py` | Login, refresh, logout, current-user profile. |
| `backend/app/api/routes/users.py` | Admin-only user management (list, create, update, deactivate). |
| `backend/app/api/routes/patients.py` | Patient CRUD, search, archive, and sub-resource management. |
| `backend/app/api/routes/doctors.py` | Doctor CRUD. |
| `backend/app/api/routes/medical_acts.py` | Medical act catalog CRUD + price history. |
| `backend/app/api/routes/consultations.py` | Consultation creation (vitals, acts, prescriptions), read, update. |
| `backend/app/api/routes/appointments.py` | Appointment CRUD, conflict-checked, cancellation. |
| `backend/alembic/` | Versioned schema migrations (Alembic), pointed at the app's settings. |
| `database/seed.py` | Bootstraps roles, permissions, role→permission grants, SUPER_ADMIN user, demo patients, demo medical act catalog, and a demo doctor. |
| `frontend/index.html` + `js/app.js` + `js/auth.js` + `js/patients.js` | Boot screen → login form → authenticated view with a fully functional patients list/search/create/archive. |
| `docker-compose.yml` | Runs `clinic-api`, `postgres`, and `redis` together with healthchecks. |

*(The Phase 4 modules — doctors, medical acts, consultations,
appointments — are fully functional via the API/`/docs`, but don't yet
have dedicated frontend screens; those arrive with the full clinical UI
during Phase 9's dashboard work, alongside the patients screen getting
its visual polish.)*

---

## 3. Install on Windows (no Docker)

```bat
:: 1. Go to the backend folder
cd clinic-os\backend

:: 2. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate

:: 3. Install dependencies
pip install -r requirements.txt

:: 4. Configure environment
copy .env.example .env
:: then edit .env with your real PostgreSQL credentials

:: 5. Make sure PostgreSQL is running and the database exists, e.g.:
::    createdb -U postgres clinic_os
:: (or create it with pgAdmin / psql)

:: 6. Run database migrations
alembic upgrade head

:: 7. Seed roles, permissions, the SUPER_ADMIN user, demo patients,
::    the medical act catalog, and a demo doctor
python ..\database\seed.py

:: 8. Start the API
uvicorn app.main:app --reload
```

The API will be available at:

```text
http://127.0.0.1:8000
http://127.0.0.1:8000/docs      (Swagger UI)
http://127.0.0.1:8000/redoc     (ReDoc)
```

From `/docs`: log in via `POST /api/auth/login` with `admin` /
`ChangeMe123!`, copy the `access_token`, click **Authorize**, paste it
as `Bearer <token>`. Then try:
- `GET /api/medical-acts` — see the 10 seeded catalog entries with their current prices.
- `GET /api/doctors` — see Dr. Cheikh Fall.
- `POST /api/consultations` with a `patient_id` (from `GET /api/patients`), a `doctor_id`, and an `acts` array referencing a medical act ID — watch the price get snapshotted onto the response.
- `POST /api/appointments` twice with the same doctor and `scheduled_at` — the second call returns `409`.

### Serve the frontend

```bat
cd clinic-os\frontend
python -m http.server 5500
```

Open `http://127.0.0.1:5500`, log in with `admin` / `ChangeMe123!` to
use the working patients screen. The Phase 4 modules are API-only for
now (see note above).

---

## 4. Install with Docker (recommended — simplest path)

Docker bundles PostgreSQL, Redis, the backend, and the frontend together,
so there's no separate Python/PostgreSQL install or manual database
setup — just one prerequisite (Docker Desktop) and one command.

```bash
copy backend\.env.example backend\.env   # Windows
# cp backend/.env.example backend/.env   # macOS/Linux

docker compose up -d --build

:: then, once the containers are healthy:
docker compose exec clinic-api alembic upgrade head
docker compose exec clinic-api python database/seed.py
```

Or use the one-click launcher: place `Demarrer-CLINIC-OS-Docker.bat` at
the repo root (next to `docker-compose.yml`) and double-click it — it
handles all of the above (build, migrate, seed, open the browser) and
waits for the server to actually be ready before opening
`http://127.0.0.1:5500`. `Arreter-CLINIC-OS-Docker.bat` stops everything
(data is preserved for next time).

Check status:

```bash
docker compose ps
curl http://localhost:8000/api/health
```

The frontend is served by an nginx container on `http://localhost:5500`
— no local Python needed for it either.

---

## 5. Testing

Automated tests cover all four phases and run against whatever database
`DATABASE_URL` points to (no mocking of the DB layer):

```bash
cd backend
pytest
```

Expected: `24 passed` — 2 health-check tests, 7 auth/RBAC tests, 7
patient tests, and 8 Phase 4 tests (doctor create/list, price history
never overwritten with a future-dated price, duplicate act code
rejected, sequential consultation numbering + BMI calculation, act
price snapshot survives a later catalog price change, consultation
with prescription, appointment conflict detection + cancellation frees
the slot, RBAC blocking a pharmacist from `/api/appointments`).

Manual smoke test:

```bash
curl http://127.0.0.1:8000/api/health
```

Expected response:

```json
{
  "success": true,
  "data": {
    "status": "ok",
    "app": "CLINIC OS",
    "environment": "development",
    "database": "connected"
  },
  "message": "CLINIC OS API is running."
}
```

If `database` shows `"unreachable"`, check that PostgreSQL is running
and that `DATABASE_URL` in `.env` matches your credentials.

---

## 6. What's next

Once Phase 4 is confirmed working on your machine (the catalog and
demo doctor appear, creating a consultation with linked acts snapshots
the price correctly, booking two overlapping appointments for the same
doctor returns a 409, and `pytest` passes), the next step is
**Phase 5 — Laboratoire** (lab test orders, sample tracking, results,
validation workflow), to be built only after this phase is validated.




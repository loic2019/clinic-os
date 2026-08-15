"""
Aggregates all route modules into a single API router.

Phase 1 wired up `/api/health`. Phase 2 added `/api/auth` and
`/api/users`. Phase 3 added `/api/patients`. Phase 4 adds `/api/doctors`,
`/api/medical-acts`, `/api/consultations`, `/api/appointments`. Later
phases will add: /api/laboratory, /api/imaging, /api/pharmacy,
/api/hospitalization, /api/emergency, /api/invoices, /api/payments,
/api/cash, /api/accounting, /api/inventory, /api/suppliers, /api/hr,
/api/payroll, /api/reports, /api/notifications, /api/audit,
/api/dashboard, /api/search, /api/ai
"""

from fastapi import APIRouter

from app.api.routes import appointments, auth, consultations, doctors, health, medical_acts, patients, users

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router, tags=["Auth"])
api_router.include_router(users.router, tags=["Users"])
api_router.include_router(patients.router, tags=["Patients"])
api_router.include_router(doctors.router, tags=["Doctors"])
api_router.include_router(medical_acts.router, tags=["Medical Acts"])
api_router.include_router(consultations.router, tags=["Consultations"])
api_router.include_router(appointments.router, tags=["Appointments"])

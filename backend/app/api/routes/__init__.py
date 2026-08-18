"""
Aggregates all route modules into a single API router.

Phase 1 wired up `/api/health`. Phase 2 added `/api/auth` and
`/api/users`. Phase 3 added `/api/patients`. Phase 4 added
`/api/doctors`, `/api/medical-acts`, `/api/consultations`,
`/api/appointments`. Phase 5 added `/api/laboratory`. Phase 7-8 added
`/api/invoices`, `/api/payments`, `/api/cash`. Phase 9 adds
`/api/accounting`. Later phases will add: /api/imaging, /api/pharmacy,
/api/hospitalization, /api/emergency, /api/inventory, /api/suppliers,
/api/hr, /api/payroll, /api/reports, /api/notifications, /api/audit,
/api/dashboard, /api/search, /api/ai
"""

from fastapi import APIRouter

from app.api.routes import (
    accounting,
    appointments,
    auth,
    cash,
    consultations,
    doctors,
    health,
    invoices,
    laboratory,
    medical_acts,
    patients,
    payments,
    users,
)

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router, tags=["Auth"])
api_router.include_router(users.router, tags=["Users"])
api_router.include_router(patients.router, tags=["Patients"])
api_router.include_router(doctors.router, tags=["Doctors"])
api_router.include_router(medical_acts.router, tags=["Medical Acts"])
api_router.include_router(consultations.router, tags=["Consultations"])
api_router.include_router(appointments.router, tags=["Appointments"])
api_router.include_router(laboratory.router, tags=["Laboratory"])
api_router.include_router(invoices.router, tags=["Invoices"])
api_router.include_router(payments.router, tags=["Payments"])
api_router.include_router(cash.router, tags=["Cash"])
api_router.include_router(accounting.router, tags=["Accounting"])

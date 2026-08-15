"""
CLINIC OS -- Demonstration / bootstrap data seeder.

Phase 2 seeds:
  - the fixed role catalog (spec section 29)
  - an initial permission catalog covering the modules defined so far
  - role -> permission grants (SUPER_ADMIN gets everything)
  - one initial SUPER_ADMIN user so you can log in for the first time

Usage:
    cd backend
    python ../database/seed.py

Re-running is safe: existing roles/permissions/users are left untouched
(matched by unique name / code / username).
"""

import asyncio
import os
import sys

# Two contexts this script runs in:
#  - Local dev: `cd backend && python ../database/seed.py`
#    -> this file's folder is .../database, backend/ is a sibling.
#  - Docker: `docker compose exec clinic-api python database/seed.py`
#    -> cwd is /app (== backend/ contents copied to image root),
#       and this file was copied to /app/database/seed.py.
_LOCAL_BACKEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
_DOCKER_BACKEND = "/app"
for _candidate in (_LOCAL_BACKEND, _DOCKER_BACKEND):
    if os.path.isdir(os.path.join(_candidate, "app")):
        sys.path.append(_candidate)
        break

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.role import Permission, Role  # noqa: E402
from app.models.user import User  # noqa: E402

ROLE_NAMES = [
    "SUPER_ADMIN",
    "ADMIN",
    "DIRECTOR",
    "DOCTOR",
    "NURSE",
    "LAB_TECHNICIAN",
    "PHARMACIST",
    "ACCOUNTANT",
    "HR_MANAGER",
    "CASHIER",
    "RECEPTIONIST",
]

# module -> list of (action, description)
PERMISSION_CATALOG: dict[str, list[tuple[str, str]]] = {
    "patients": [("read", "Voir les patients"), ("create", "Creer un patient"), ("update", "Modifier un patient")],
    "medical_records": [("read", "Voir les dossiers medicaux"), ("create", "Creer une entree medicale"), ("update", "Modifier un dossier medical")],
    "consultations": [("read", "Voir les consultations"), ("create", "Creer une consultation"), ("update", "Modifier une consultation")],
    "billing": [("read", "Voir les factures"), ("create", "Creer une facture"), ("update", "Modifier une facture")],
    "payments": [("read", "Voir les paiements"), ("create", "Encaisser un paiement")],
    "cash": [("open", "Ouvrir une caisse"), ("close", "Cloturer une caisse")],
    "refund": [("request", "Demander un remboursement"), ("approve", "Approuver un remboursement")],
    "invoice": [("cancel_request", "Demander l'annulation d'une facture"), ("cancel_approve", "Approuver l'annulation d'une facture")],
    "accounting": [("read", "Voir la comptabilite"), ("create", "Creer une ecriture comptable")],
    "hr": [("read", "Voir les donnees RH"), ("create", "Creer un employe"), ("update", "Modifier un employe")],
    "users": [("read", "Voir les utilisateurs"), ("create", "Creer un utilisateur"), ("update", "Modifier un utilisateur")],
    "audit": [("read", "Consulter le journal d'audit")],
    "doctors": [("read", "Voir les medecins"), ("create", "Creer un medecin"), ("update", "Modifier un medecin")],
    "medical_acts": [("read", "Voir le catalogue des actes"), ("create", "Creer un acte medical"), ("update", "Modifier un acte medical (y compris les prix)")],
    "appointments": [("read", "Voir les rendez-vous"), ("create", "Creer un rendez-vous"), ("update", "Modifier un rendez-vous")],
}

# Which roles get which modules fully (all actions) -- a simplified
# starting point; fine-grained per-action grants can be adjusted later
# from the (future) permissions administration screen.
ROLE_MODULE_GRANTS: dict[str, list[str]] = {
    "SUPER_ADMIN": list(PERMISSION_CATALOG.keys()),  # everything
    "ADMIN": ["patients", "medical_records", "consultations", "billing", "payments", "hr", "users", "audit", "doctors", "medical_acts", "appointments"],
    "DIRECTOR": ["patients", "consultations", "billing", "accounting", "hr", "audit", "doctors", "medical_acts", "appointments"],
    "DOCTOR": ["patients", "medical_records", "consultations", "appointments", "medical_acts", "doctors"],
    "NURSE": ["patients", "consultations", "appointments"],
    "LAB_TECHNICIAN": ["patients", "medical_records"],
    "PHARMACIST": ["patients", "medical_records"],
    "ACCOUNTANT": ["billing", "payments", "accounting"],
    "HR_MANAGER": ["hr", "doctors"],
    "CASHIER": ["patients", "billing", "payments", "cash", "refund", "invoice"],
    "RECEPTIONIST": ["patients", "consultations", "appointments", "doctors"],
}

SUPER_ADMIN_USERNAME = "admin"
SUPER_ADMIN_EMAIL = "admin@clinic-os.local"
SUPER_ADMIN_PASSWORD = "ChangeMe123!"  # noqa: S105 -- change immediately after first login
SUPER_ADMIN_FULL_NAME = "Administrateur Systeme"


async def get_or_create_role(session, name: str) -> Role:
    result = await session.execute(
        select(Role).where(Role.name == name).options(selectinload(Role.permissions))
    )
    role = result.scalar_one_or_none()
    if role is None:
        # Setting permissions=[] populates the in-memory collection right
        # away, so accessing role.permissions later never needs an
        # implicit (and, under AsyncSession, unsafe) lazy load.
        role = Role(name=name, description=f"Role {name}", permissions=[])
        session.add(role)
        await session.flush()
    return role


async def get_or_create_permission(session, module: str, action: str, description: str) -> Permission:
    code = f"{module}.{action}"
    result = await session.execute(select(Permission).where(Permission.code == code))
    permission = result.scalar_one_or_none()
    if permission is None:
        permission = Permission(code=code, module=module, description=description)
        session.add(permission)
        await session.flush()
    return permission


async def seed_demo_patients(session) -> None:
    """Adds a small set of demo patients if none exist yet, so the UI
    isn't empty on first login. Full-scale demo data generation (100+
    patients, consultations, invoices, etc.) is spec section 70's job,
    once those modules exist."""
    from sqlalchemy import func

    from datetime import date as date_cls

    from app.models.patient import Patient
    from app.services.numbering_service import generate_number

    count = (await session.execute(select(func.count()).select_from(Patient))).scalar_one()
    if count > 0:
        print(f"Patients : {count} deja presents, seed de demo ignore.")
        return

    demo_patients = [
        ("Awa", "Diallo", date_cls(1990, 5, 14), "F", "+221701234567"),
        ("Ibrahima", "Sow", date_cls(1985, 11, 2), "M", "+221702345678"),
        ("Fatou", "Ndiaye", date_cls(1998, 3, 21), "F", "+221703456789"),
        ("Moussa", "Ba", date_cls(1975, 7, 30), "M", "+221704567890"),
        ("Aissatou", "Gueye", date_cls(2001, 1, 9), "F", "+221705678901"),
    ]

    for first_name, last_name, dob, gender, phone in demo_patients:
        patient_number = await generate_number(session, key="PAT", prefix="PAT")
        patient = Patient(
            patient_number=patient_number,
            first_name=first_name,
            last_name=last_name,
            date_of_birth=dob,
            gender=gender,
            phone=phone,
        )
        session.add(patient)

    await session.commit()
    print(f"Patients de demonstration : {len(demo_patients)} crees.")


async def seed_demo_medical_data(session) -> None:
    """Adds a starter medical act catalog (spec section 13 examples) and
    one demo doctor, if none exist yet."""
    from datetime import date as date_cls

    from sqlalchemy import func

    from app.models.doctor import Doctor
    from app.models.medical_act import MedicalAct, MedicalActPrice

    act_count = (await session.execute(select(func.count()).select_from(MedicalAct))).scalar_one()
    if act_count == 0:
        catalog = [
            ("CONS-001", "Consultation generale", "Consultation", 10000),
            ("CONS-002", "Consultation specialisee", "Consultation", 15000),
            ("ACT-001", "Injection", "Acte", 2000),
            ("ACT-002", "Perfusion", "Acte", 5000),
            ("ACT-003", "Pansement", "Acte", 1500),
            ("ACT-004", "Suture", "Acte", 8000),
            ("LAB-001", "NFS", "Laboratoire", 8000),
            ("LAB-002", "Glycemie", "Laboratoire", 3000),
            ("IMG-001", "Echographie", "Imagerie", 20000),
            ("IMG-002", "Radiographie", "Imagerie", 15000),
        ]
        for code, name, category, price in catalog:
            act = MedicalAct(code=code, name=name, category=category)
            act.prices = [MedicalActPrice(price=price, effective_from=date_cls.today())]
            session.add(act)
        print(f"Catalogue des actes medicaux : {len(catalog)} actes crees.")
    else:
        print(f"Actes medicaux : {act_count} deja presents, seed de demo ignore.")

    doctor_count = (await session.execute(select(func.count()).select_from(Doctor))).scalar_one()
    if doctor_count == 0:
        doctor = Doctor(
            first_name="Cheikh",
            last_name="Fall",
            specialty="Medecine generale",
            phone="+221706789012",
        )
        session.add(doctor)
        print("Medecin de demonstration : Dr. Cheikh Fall cree.")
    else:
        print(f"Medecins : {doctor_count} deja presents, seed de demo ignore.")

    await session.commit()


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        # --- Roles ---
        roles_by_name: dict[str, Role] = {}
        for name in ROLE_NAMES:
            roles_by_name[name] = await get_or_create_role(session, name)
        print(f"Roles : {len(roles_by_name)} prets.")

        # --- Permissions ---
        permissions_by_code: dict[str, Permission] = {}
        for module, actions in PERMISSION_CATALOG.items():
            for action, description in actions:
                perm = await get_or_create_permission(session, module, action, description)
                permissions_by_code[perm.code] = perm
        print(f"Permissions : {len(permissions_by_code)} pretes.")

        # --- Role -> Permission grants ---
        for role_name, modules in ROLE_MODULE_GRANTS.items():
            role = roles_by_name[role_name]
            granted_codes = {
                code for code in permissions_by_code if code.split(".")[0] in modules
            }
            existing_codes = {p.code for p in role.permissions}
            missing = granted_codes - existing_codes
            if missing:
                role.permissions.extend(permissions_by_code[c] for c in missing)
        await session.flush()
        print("Attribution des permissions aux roles : terminee.")

        # --- Initial SUPER_ADMIN user ---
        result = await session.execute(select(User).where(User.username == SUPER_ADMIN_USERNAME))
        admin_user = result.scalar_one_or_none()
        if admin_user is None:
            admin_user = User(
                username=SUPER_ADMIN_USERNAME,
                email=SUPER_ADMIN_EMAIL,
                full_name=SUPER_ADMIN_FULL_NAME,
                hashed_password=hash_password(SUPER_ADMIN_PASSWORD),
                must_change_password=True,
                roles=[roles_by_name["SUPER_ADMIN"]],
            )
            session.add(admin_user)
            print(
                f"Utilisateur SUPER_ADMIN cree : {SUPER_ADMIN_USERNAME} / {SUPER_ADMIN_PASSWORD} "
                "(a changer immediatement apres la premiere connexion)."
            )
        else:
            print("Utilisateur SUPER_ADMIN deja present, non modifie.")

        await session.commit()
        print("Seed termine avec succes.")

        await seed_demo_patients(session)
        await seed_demo_medical_data(session)


if __name__ == "__main__":
    asyncio.run(seed())

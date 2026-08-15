"""
GET    /api/patients                      list, search, filter, paginate
POST   /api/patients                       create
GET    /api/patients/{id}                   detail (incl. contacts, insurances, allergies, history)
PUT    /api/patients/{id}                   update
POST   /api/patients/{id}/archive           archive (soft delete — never a hard delete, spec section 10)
POST   /api/patients/{id}/unarchive          restore

POST   /api/patients/{id}/contacts          add a "personne à contacter"
DELETE /api/patients/{id}/contacts/{cid}

POST   /api/patients/{id}/insurances        add an insurance record
DELETE /api/patients/{id}/insurances/{iid}

POST   /api/patients/{id}/allergies         add an allergy
DELETE /api/patients/{id}/allergies/{aid}

POST   /api/patients/{id}/medical-history   add an antécédent entry
DELETE /api/patients/{id}/medical-history/{hid}

All routes require the matching `patients.*` permission (spec section 29).
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user, require_permission
from app.models.user import User
from app.schemas.patient import (
    MedicalHistoryCreate,
    MedicalHistoryRead,
    PatientAllergyCreate,
    PatientAllergyRead,
    PatientContactCreate,
    PatientContactRead,
    PatientCreate,
    PatientInsuranceCreate,
    PatientInsuranceRead,
    PatientListItem,
    PatientListResponse,
    PatientRead,
    PatientUpdate,
)
from app.services.patient_service import PatientService

router = APIRouter(prefix="/patients")


@router.get("", response_model=None, dependencies=[Depends(require_permission("patients.read"))])
async def list_patients(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    gender: str | None = Query(default=None),
    include_archived: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
):
    service = PatientService(db)
    items, total = await service.list_patients(
        page=page, page_size=page_size, search=search, gender=gender, include_archived=include_archived
    )
    data = PatientListResponse(
        items=[PatientListItem.model_validate(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
    )
    return {"success": True, "data": data, "message": "OK"}


@router.post("", response_model=None, dependencies=[Depends(require_permission("patients.create"))])
async def create_patient(
    payload: PatientCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = PatientService(db)
    patient = await service.create_patient(payload, created_by_id=current_user.id)
    await db.commit()
    return {
        "success": True,
        "data": PatientRead.model_validate(patient),
        "message": f"Patient {patient.patient_number} créé.",
    }


@router.get(
    "/{patient_id}", response_model=None, dependencies=[Depends(require_permission("patients.read"))]
)
async def get_patient(patient_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = PatientService(db)
    patient = await service.get_patient(patient_id)
    return {"success": True, "data": PatientRead.model_validate(patient), "message": "OK"}


@router.put(
    "/{patient_id}", response_model=None, dependencies=[Depends(require_permission("patients.update"))]
)
async def update_patient(patient_id: uuid.UUID, payload: PatientUpdate, db: AsyncSession = Depends(get_db)):
    service = PatientService(db)
    patient = await service.update_patient(patient_id, payload)
    await db.commit()
    return {"success": True, "data": PatientRead.model_validate(patient), "message": "Patient mis à jour."}


@router.post(
    "/{patient_id}/archive",
    response_model=None,
    dependencies=[Depends(require_permission("patients.update"))],
)
async def archive_patient(patient_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = PatientService(db)
    patient = await service.archive_patient(patient_id)
    await db.commit()
    return {"success": True, "data": PatientRead.model_validate(patient), "message": "Patient archivé."}


@router.post(
    "/{patient_id}/unarchive",
    response_model=None,
    dependencies=[Depends(require_permission("patients.update"))],
)
async def unarchive_patient(patient_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = PatientService(db)
    patient = await service.unarchive_patient(patient_id)
    await db.commit()
    return {"success": True, "data": PatientRead.model_validate(patient), "message": "Patient restauré."}


# --- Contacts --------------------------------------------------------------


@router.post(
    "/{patient_id}/contacts",
    response_model=None,
    dependencies=[Depends(require_permission("patients.update"))],
)
async def add_contact(patient_id: uuid.UUID, payload: PatientContactCreate, db: AsyncSession = Depends(get_db)):
    service = PatientService(db)
    contact = await service.add_contact(patient_id, payload)
    await db.commit()
    return {"success": True, "data": PatientContactRead.model_validate(contact), "message": "Contact ajouté."}


@router.delete(
    "/{patient_id}/contacts/{contact_id}",
    response_model=None,
    dependencies=[Depends(require_permission("patients.update"))],
)
async def remove_contact(patient_id: uuid.UUID, contact_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = PatientService(db)
    await service.remove_contact(patient_id, contact_id)
    await db.commit()
    return {"success": True, "data": None, "message": "Contact supprimé."}


# --- Insurances --------------------------------------------------------------


@router.post(
    "/{patient_id}/insurances",
    response_model=None,
    dependencies=[Depends(require_permission("patients.update"))],
)
async def add_insurance(
    patient_id: uuid.UUID, payload: PatientInsuranceCreate, db: AsyncSession = Depends(get_db)
):
    service = PatientService(db)
    insurance = await service.add_insurance(patient_id, payload)
    await db.commit()
    return {
        "success": True,
        "data": PatientInsuranceRead.model_validate(insurance),
        "message": "Assurance ajoutée.",
    }


@router.delete(
    "/{patient_id}/insurances/{insurance_id}",
    response_model=None,
    dependencies=[Depends(require_permission("patients.update"))],
)
async def remove_insurance(
    patient_id: uuid.UUID, insurance_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    service = PatientService(db)
    await service.remove_insurance(patient_id, insurance_id)
    await db.commit()
    return {"success": True, "data": None, "message": "Assurance supprimée."}


# --- Allergies --------------------------------------------------------------


@router.post(
    "/{patient_id}/allergies",
    response_model=None,
    dependencies=[Depends(require_permission("patients.update"))],
)
async def add_allergy(patient_id: uuid.UUID, payload: PatientAllergyCreate, db: AsyncSession = Depends(get_db)):
    service = PatientService(db)
    allergy = await service.add_allergy(patient_id, payload)
    await db.commit()
    return {"success": True, "data": PatientAllergyRead.model_validate(allergy), "message": "Allergie ajoutée."}


@router.delete(
    "/{patient_id}/allergies/{allergy_id}",
    response_model=None,
    dependencies=[Depends(require_permission("patients.update"))],
)
async def remove_allergy(patient_id: uuid.UUID, allergy_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = PatientService(db)
    await service.remove_allergy(patient_id, allergy_id)
    await db.commit()
    return {"success": True, "data": None, "message": "Allergie supprimée."}


# --- Medical history ---------------------------------------------------------


@router.post(
    "/{patient_id}/medical-history",
    response_model=None,
    dependencies=[Depends(require_permission("medical_records.update"))],
)
async def add_medical_history(
    patient_id: uuid.UUID, payload: MedicalHistoryCreate, db: AsyncSession = Depends(get_db)
):
    service = PatientService(db)
    entry = await service.add_medical_history(patient_id, payload)
    await db.commit()
    return {
        "success": True,
        "data": MedicalHistoryRead.model_validate(entry),
        "message": "Antécédent ajouté.",
    }


@router.delete(
    "/{patient_id}/medical-history/{history_id}",
    response_model=None,
    dependencies=[Depends(require_permission("medical_records.update"))],
)
async def remove_medical_history(
    patient_id: uuid.UUID, history_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    service = PatientService(db)
    await service.remove_medical_history(patient_id, history_id)
    await db.commit()
    return {"success": True, "data": None, "message": "Antécédent supprimé."}

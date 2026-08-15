"""Laboratory business logic (spec section 36)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ClinicOSException, ConflictError, NotFoundError
from app.models.laboratory import (
    LabItemStatus,
    LabOrder,
    LabOrderItem,
    LabOrderStatus,
    LabResult,
    LabSample,
    LabTestCatalog,
)
from app.repositories.laboratory_repository import LabOrderRepository, LabTestRepository
from app.repositories.patient_repository import PatientRepository
from app.schemas.laboratory import (
    LabOrderCreate,
    LabResultInput,
    LabSampleCreate,
    LabTestCreate,
    LabTestUpdate,
)
from app.services.numbering_service import generate_number

ORDER_NUMBER_KEY = "LAB"
ORDER_NUMBER_PREFIX = "LAB"


class LabTestService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.tests = LabTestRepository(db)

    async def create_test(self, payload: LabTestCreate) -> LabTestCatalog:
        if await self.tests.get_by_code(payload.code):
            raise ConflictError(f"Le code '{payload.code}' est déjà utilisé.")
        test = LabTestCatalog(**payload.model_dump())
        return await self.tests.create(test)

    async def get_test(self, test_id: uuid.UUID) -> LabTestCatalog:
        test = await self.tests.get_by_id(test_id)
        if test is None:
            raise NotFoundError("Analyse introuvable dans le catalogue.")
        return test

    async def list_tests(self, *, page: int, page_size: int, search: str | None, active_only: bool):
        return await self.tests.list_paginated(page=page, page_size=page_size, search=search, active_only=active_only)

    async def update_test(self, test_id: uuid.UUID, payload: LabTestUpdate) -> LabTestCatalog:
        test = await self.get_test(test_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(test, field, value)
        return await self.tests.save(test)


class LabOrderService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.orders = LabOrderRepository(db)
        self.tests = LabTestRepository(db)
        self.patients = PatientRepository(db)

    async def create_order(self, payload: LabOrderCreate, *, created_by_id: uuid.UUID | None) -> LabOrder:
        patient = await self.patients.get_by_id(payload.patient_id, include_archived=False)
        if patient is None:
            raise NotFoundError("Patient introuvable.")

        order_number = await generate_number(self.db, key=ORDER_NUMBER_KEY, prefix=ORDER_NUMBER_PREFIX)

        order = LabOrder(
            order_number=order_number,
            patient_id=payload.patient_id,
            doctor_id=payload.doctor_id,
            consultation_id=payload.consultation_id,
            notes=payload.notes,
            created_by_id=created_by_id,
        )

        for test_id in payload.lab_test_ids:
            test = await self.tests.get_by_id(test_id)
            if test is None:
                raise NotFoundError(f"Analyse introuvable dans le catalogue : {test_id}")
            order.items.append(LabOrderItem(lab_test_id=test.id, test_name_snapshot=test.name))

        return await self.orders.create(order)

    async def get_order(self, order_id: uuid.UUID) -> LabOrder:
        order = await self.orders.get_by_id(order_id)
        if order is None:
            raise NotFoundError("Commande de laboratoire introuvable.")
        return order

    async def list_orders(self, *, page: int, page_size: int, patient_id: uuid.UUID | None, status: str | None):
        return await self.orders.list_paginated(page=page, page_size=page_size, patient_id=patient_id, status=status)

    async def add_sample(self, order_id: uuid.UUID, payload: LabSampleCreate, *, collected_by_id: uuid.UUID | None) -> LabOrder:
        order = await self.get_order(order_id)

        sample = LabSample(
            order_id=order.id,
            sample_type=payload.sample_type,
            collected_at=payload.collected_at or datetime.now(timezone.utc),
            collected_by_id=collected_by_id,
            notes=payload.notes,
        )
        self.db.add(sample)

        for item in order.items:
            if item.status == LabItemStatus.PENDING:
                item.status = LabItemStatus.SAMPLE_COLLECTED

        if order.status == LabOrderStatus.ORDERED:
            order.status = LabOrderStatus.IN_PROGRESS

        await self.db.flush()
        return await self.get_order(order_id)

    async def enter_result(
        self, order_id: uuid.UUID, item_id: uuid.UUID, payload: LabResultInput, *, entered_by_id: uuid.UUID | None
    ) -> LabOrder:
        item = await self.orders.get_item(order_id, item_id)
        if item is None:
            raise NotFoundError("Analyse introuvable dans cette commande.")
        if item.status == LabItemStatus.VALIDATED:
            raise ConflictError("Ce résultat est déjà validé et ne peut plus être modifié directement.")

        test = await self.tests.get_by_id(item.lab_test_id)
        is_abnormal = False
        if payload.value_numeric is not None and test is not None:
            if test.reference_range_low is not None and payload.value_numeric < test.reference_range_low:
                is_abnormal = True
            if test.reference_range_high is not None and payload.value_numeric > test.reference_range_high:
                is_abnormal = True

        reference_display = None
        if test is not None:
            if test.reference_range_low is not None and test.reference_range_high is not None:
                reference_display = f"{test.reference_range_low} - {test.reference_range_high} {test.unit or ''}".strip()
            elif test.reference_range_text:
                reference_display = test.reference_range_text

        if item.result is None:
            item.result = LabResult(order_item_id=item.id)

        item.result.value_numeric = payload.value_numeric
        item.result.value_text = payload.value_text
        item.result.unit = test.unit if test else None
        item.result.reference_range_display = reference_display
        item.result.is_abnormal = is_abnormal
        item.result.notes = payload.notes
        item.result.entered_by_id = entered_by_id
        item.result.entered_at = datetime.now(timezone.utc)

        item.status = LabItemStatus.RESULT_ENTERED

        await self.db.flush()
        return await self.get_order(order_id)

    async def validate_result(
        self, order_id: uuid.UUID, item_id: uuid.UUID, *, validated_by_id: uuid.UUID | None
    ) -> LabOrder:
        item = await self.orders.get_item(order_id, item_id)
        if item is None:
            raise NotFoundError("Analyse introuvable dans cette commande.")
        if item.result is None:
            raise ClinicOSException("Aucun résultat n'a encore été saisi pour cette analyse.", code="NO_RESULT")
        if item.status != LabItemStatus.RESULT_ENTERED:
            raise ConflictError("Ce résultat n'est pas en attente de validation.")

        item.result.validated_by_id = validated_by_id
        item.result.validated_at = datetime.now(timezone.utc)
        item.status = LabItemStatus.VALIDATED

        order = await self.get_order(order_id)
        if all(i.status in (LabItemStatus.VALIDATED, LabItemStatus.CANCELLED) for i in order.items):
            order.status = LabOrderStatus.COMPLETED

        await self.db.flush()
        return await self.get_order(order_id)

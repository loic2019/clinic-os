"""Medical act catalog business logic (spec sections 13-14)."""

import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.medical_act import MedicalAct, MedicalActPrice
from app.repositories.medical_act_repository import MedicalActRepository
from app.schemas.medical_act import MedicalActCreate, MedicalActPriceCreate, MedicalActUpdate


class MedicalActService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.acts = MedicalActRepository(db)

    async def create_act(self, payload: MedicalActCreate) -> MedicalAct:
        if await self.acts.get_by_code(payload.code):
            raise ConflictError(f"Le code '{payload.code}' est déjà utilisé.")

        act = MedicalAct(
            code=payload.code,
            name=payload.name,
            category=payload.category,
            description=payload.description,
            tax_rate=payload.tax_rate,
            service=payload.service,
            duration_minutes=payload.duration_minutes,
        )
        act.prices = [MedicalActPrice(price=payload.initial_price, effective_from=date.today())]
        return await self.acts.create(act)

    async def get_act(self, act_id: uuid.UUID) -> MedicalAct:
        act = await self.acts.get_by_id(act_id)
        if act is None:
            raise NotFoundError("Acte médical introuvable.")
        return act

    async def list_acts(
        self, *, page: int, page_size: int, search: str | None, category: str | None, active_only: bool
    ):
        return await self.acts.list_paginated(
            page=page, page_size=page_size, search=search, category=category, active_only=active_only
        )

    async def update_act(self, act_id: uuid.UUID, payload: MedicalActUpdate) -> MedicalAct:
        act = await self.get_act(act_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(act, field, value)
        return await self.acts.save(act)

    async def add_price(self, act_id: uuid.UUID, payload: MedicalActPriceCreate) -> MedicalAct:
        """Never overwrites: always inserts a new price history row (spec section 14)."""
        act = await self.get_act(act_id)
        price = MedicalActPrice(
            medical_act_id=act.id,
            price=payload.price,
            effective_from=payload.effective_from or date.today(),
        )
        await self.acts.add_price(price)
        # `act` is already in the session identity map with its `prices`
        # collection loaded from an earlier query — adding a sibling row
        # directly via the repository doesn't update that in-memory
        # collection, so without an explicit refresh the caller would see
        # a stale, pre-insert price list even though the new row is
        # already committed.
        await self.db.refresh(act, attribute_names=["prices"])
        return act

    async def deactivate_act(self, act_id: uuid.UUID) -> MedicalAct:
        act = await self.get_act(act_id)
        act.is_active = False
        return await self.acts.save(act)

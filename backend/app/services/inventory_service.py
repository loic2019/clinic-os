"""
Inventory business logic (spec section 45).

The core piece of care here is FEFO (First Expired, First Out — spec
section 37) consumption: when stock goes out (SALE, DISPENSATION,
EXPIRATION, or a negative ADJUSTMENT), it is drawn from the batch
expiring soonest first, then the next soonest, and so on, spilling
across batches as needed. Batches with no expiration date are treated
as expiring "last" (never), so dated batches are always used up before
undated ones.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ClinicOSException, ConflictError, NotFoundError
from app.models.inventory import (
    INBOUND_MOVEMENT_TYPES,
    OUTBOUND_MOVEMENT_TYPES,
    InventoryBatch,
    InventoryItem,
    InventoryMovement,
    MovementType,
)
from app.repositories.inventory_repository import InventoryRepository
from app.schemas.inventory import (
    ExpiryAlert,
    InventoryAlerts,
    InventoryItemCreate,
    InventoryItemUpdate,
    LowStockAlert,
    MovementCreate,
)

# Batches with no expiration date sort after every dated batch in FEFO
# order — a far-future sentinel is simpler than special-casing None
# everywhere a comparison happens.
_NO_EXPIRY_SENTINEL = date.max


class InventoryService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.inventory = InventoryRepository(db)

    # --- Items ---

    async def create_item(self, payload: InventoryItemCreate) -> InventoryItem:
        if await self.inventory.get_item_by_code(payload.code):
            raise ConflictError(f"Le code '{payload.code}' est déjà utilisé.")
        item = InventoryItem(**payload.model_dump())
        return await self.inventory.create_item(item)

    async def get_item(self, item_id: uuid.UUID) -> InventoryItem:
        item = await self.inventory.get_item_by_id(item_id)
        if item is None:
            raise NotFoundError("Article introuvable dans le stock.")
        return item

    async def list_items(
        self, *, page: int, page_size: int, search: str | None, category: str | None, active_only: bool
    ):
        return await self.inventory.list_items_paginated(
            page=page, page_size=page_size, search=search, category=category, active_only=active_only
        )

    async def update_item(self, item_id: uuid.UUID, payload: InventoryItemUpdate) -> InventoryItem:
        item = await self.get_item(item_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
        return await self.inventory.save_item(item)

    # --- Receiving stock (used directly, and by PurchaseOrderService) ---

    async def receive_stock(
        self,
        *,
        item: InventoryItem,
        quantity: int,
        batch_number: str | None,
        expiry_date: date | None,
        supplier_id: uuid.UUID | None,
        reference: str | None,
        created_by_id: uuid.UUID | None,
    ) -> InventoryBatch:
        if quantity <= 0:
            raise ClinicOSException("La quantité reçue doit être positive.", code="INVALID_QUANTITY")

        batch = InventoryBatch(
            inventory_item_id=item.id,
            batch_number=batch_number,
            quantity=quantity,
            expiry_date=expiry_date,
            supplier_id=supplier_id,
            received_at=datetime.now(timezone.utc),
        )
        created_batch = await self.inventory.create_batch(batch)

        item.quantity_on_hand += quantity
        await self.inventory.save_item(item)

        await self.inventory.create_movement(
            InventoryMovement(
                inventory_item_id=item.id,
                batch_id=created_batch.id,
                movement_type=MovementType.PURCHASE,
                quantity=quantity,
                reference=reference,
                created_by_id=created_by_id,
            )
        )
        return created_batch

    # --- Recording a movement (manual dispensation/sale/adjustment/etc.) ---

    async def record_movement(
        self, item_id: uuid.UUID, payload: MovementCreate, *, created_by_id: uuid.UUID | None
    ) -> InventoryItem:
        item = await self.get_item(item_id)

        if payload.movement_type in INBOUND_MOVEMENT_TYPES:
            await self.receive_stock(
                item=item,
                quantity=payload.quantity,
                batch_number=None,
                expiry_date=None,
                supplier_id=None,
                reference=payload.reference,
                created_by_id=created_by_id,
            )
        elif payload.movement_type in OUTBOUND_MOVEMENT_TYPES:
            await self._consume_fefo(
                item,
                quantity=payload.quantity,
                movement_type=payload.movement_type,
                reference=payload.reference,
                notes=payload.notes,
                created_by_id=created_by_id,
            )
        else:
            # ADJUSTMENT / TRANSFER: sign taken directly from the caller.
            if payload.quantity > 0:
                await self.receive_stock(
                    item=item,
                    quantity=payload.quantity,
                    batch_number=None,
                    expiry_date=None,
                    supplier_id=None,
                    reference=payload.reference,
                    created_by_id=created_by_id,
                )
            elif payload.quantity < 0:
                await self._consume_fefo(
                    item,
                    quantity=-payload.quantity,
                    movement_type=payload.movement_type,
                    reference=payload.reference,
                    notes=payload.notes,
                    created_by_id=created_by_id,
                )
            else:
                raise ClinicOSException("La quantité ne peut pas être nulle.", code="INVALID_QUANTITY")

        return await self.get_item(item_id)

    async def _consume_fefo(
        self,
        item: InventoryItem,
        *,
        quantity: int,
        movement_type: MovementType,
        reference: str | None,
        notes: str | None,
        created_by_id: uuid.UUID | None,
    ) -> None:
        """Consumes `quantity` units from `item`'s batches, soonest-expiring
        first, spilling across batches as needed. Raises if total stock
        is insufficient — never allows negative stock."""
        if quantity <= 0:
            raise ClinicOSException("La quantité doit être positive.", code="INVALID_QUANTITY")

        available = item.quantity_on_hand
        if available < quantity:
            raise ConflictError(
                f"Stock insuffisant pour '{item.name}' : {available} disponible(s), {quantity} demandé(s)."
            )

        remaining_to_consume = quantity
        eligible_batches = [b for b in item.batches if b.quantity > 0]
        eligible_batches.sort(key=lambda b: b.expiry_date or _NO_EXPIRY_SENTINEL)

        for batch in eligible_batches:
            if remaining_to_consume <= 0:
                break
            take = min(batch.quantity, remaining_to_consume)
            batch.quantity -= take
            remaining_to_consume -= take
            await self.inventory.save_batch(batch)

            await self.inventory.create_movement(
                InventoryMovement(
                    inventory_item_id=item.id,
                    batch_id=batch.id,
                    movement_type=movement_type,
                    quantity=-take,
                    reference=reference,
                    notes=notes,
                    created_by_id=created_by_id,
                )
            )

        item.quantity_on_hand -= quantity
        await self.inventory.save_item(item)

    # --- Movements listing ---

    async def list_movements(self, *, page: int, page_size: int, item_id: uuid.UUID | None):
        return await self.inventory.list_movements_paginated(page=page, page_size=page_size, inventory_item_id=item_id)

    # --- Alerts ---

    async def get_alerts(self, *, expiry_horizon_days: int = 30) -> InventoryAlerts:
        all_items = await self.inventory.list_all_active_items()
        low_stock = [
            LowStockAlert(
                inventory_item_id=i.id,
                code=i.code,
                name=i.name,
                quantity_on_hand=i.quantity_on_hand,
                reorder_threshold=i.reorder_threshold,
            )
            for i in all_items
            if i.is_low_stock
        ]

        today = datetime.now(timezone.utc).date()
        horizon = today + timedelta(days=expiry_horizon_days)

        expiring_batches = await self.inventory.list_batches_expiring_between(today, horizon)
        expired_batches = await self.inventory.list_expired_batches(today)

        item_by_id = {i.id: i for i in all_items}

        def to_alert(batch) -> ExpiryAlert | None:
            item = item_by_id.get(batch.inventory_item_id)
            if item is None:
                return None
            return ExpiryAlert(
                inventory_item_id=item.id,
                item_code=item.code,
                item_name=item.name,
                batch_id=batch.id,
                batch_number=batch.batch_number,
                quantity=batch.quantity,
                expiry_date=batch.expiry_date,
                days_until_expiry=(batch.expiry_date - today).days,
            )

        expiring_soon = [a for a in (to_alert(b) for b in expiring_batches) if a is not None]
        expired = [a for a in (to_alert(b) for b in expired_batches) if a is not None]

        return InventoryAlerts(low_stock=low_stock, expiring_soon=expiring_soon, expired=expired)

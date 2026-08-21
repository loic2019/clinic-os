"""
Supplier and purchase order business logic (spec section 46):
    Demande -> Bon de commande -> Réception -> Contrôle -> Stock -> Facture -> Paiement

Receiving items is the step that actually moves the needle in
inventory: it calls InventoryService.receive_stock for each received
line (creating a batch + a PURCHASE movement), then updates the
purchase order item's quantity_received and the order's overall status
(PARTIALLY_RECEIVED vs RECEIVED) — all in one transaction, so a
partial failure never leaves stock updated without the order reflecting it.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ClinicOSException, ConflictError, NotFoundError
from app.models.supplier import PurchaseOrder, PurchaseOrderItem, PurchaseOrderStatus, Supplier
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.supplier_repository import PurchaseOrderRepository, SupplierRepository
from app.schemas.supplier import PurchaseOrderCreate, ReceiveOrderInput, SupplierCreate, SupplierUpdate
from app.services.inventory_service import InventoryService
from app.services.numbering_service import generate_number

ORDER_NUMBER_KEY = "ORD"
ORDER_NUMBER_PREFIX = "ORD"


class SupplierService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.suppliers = SupplierRepository(db)

    async def create_supplier(self, payload: SupplierCreate) -> Supplier:
        if await self.suppliers.get_by_code(payload.code):
            raise ClinicOSException(f"Le code '{payload.code}' est déjà utilisé.", code="CONFLICT")
        supplier = Supplier(**payload.model_dump())
        return await self.suppliers.create(supplier)

    async def get_supplier(self, supplier_id: uuid.UUID) -> Supplier:
        supplier = await self.suppliers.get_by_id(supplier_id)
        if supplier is None:
            raise NotFoundError("Fournisseur introuvable.")
        return supplier

    async def list_suppliers(self, *, page: int, page_size: int, search: str | None, active_only: bool):
        return await self.suppliers.list_paginated(page=page, page_size=page_size, search=search, active_only=active_only)

    async def update_supplier(self, supplier_id: uuid.UUID, payload: SupplierUpdate) -> Supplier:
        supplier = await self.get_supplier(supplier_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(supplier, field, value)
        return await self.suppliers.save(supplier)


class PurchaseOrderService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.orders = PurchaseOrderRepository(db)
        self.suppliers = SupplierRepository(db)
        self.inventory_repo = InventoryRepository(db)
        self.inventory_service = InventoryService(db)

    async def create_order(self, payload: PurchaseOrderCreate, *, created_by_id: uuid.UUID | None) -> PurchaseOrder:
        supplier = await self.suppliers.get_by_id(payload.supplier_id)
        if supplier is None:
            raise NotFoundError("Fournisseur introuvable.")

        order_number = await generate_number(self.db, key=ORDER_NUMBER_KEY, prefix=ORDER_NUMBER_PREFIX)
        order = PurchaseOrder(
            order_number=order_number,
            supplier_id=payload.supplier_id,
            notes=payload.notes,
            created_by_id=created_by_id,
            status=PurchaseOrderStatus.SUBMITTED,
        )

        for item_input in payload.items:
            inv_item = await self.inventory_repo.get_item_by_id(item_input.inventory_item_id)
            if inv_item is None:
                raise NotFoundError(f"Article de stock introuvable : {item_input.inventory_item_id}")
            order.items.append(
                PurchaseOrderItem(
                    inventory_item_id=item_input.inventory_item_id,
                    quantity_ordered=item_input.quantity_ordered,
                    unit_price=item_input.unit_price,
                )
            )

        created = await self.orders.create(order)
        return await self.orders.get_by_id(created.id)

    async def get_order(self, order_id: uuid.UUID) -> PurchaseOrder:
        order = await self.orders.get_by_id(order_id)
        if order is None:
            raise NotFoundError("Commande fournisseur introuvable.")
        return order

    async def list_orders(self, *, page: int, page_size: int, supplier_id: uuid.UUID | None, status: str | None):
        return await self.orders.list_paginated(page=page, page_size=page_size, supplier_id=supplier_id, status=status)

    async def receive_order(
        self, order_id: uuid.UUID, payload: ReceiveOrderInput, *, received_by_id: uuid.UUID | None
    ) -> PurchaseOrder:
        order = await self.get_order(order_id)
        if order.status in (PurchaseOrderStatus.RECEIVED, PurchaseOrderStatus.CANCELLED):
            raise ConflictError("Cette commande est déjà entièrement reçue ou annulée.")

        for line in payload.items:
            order_item = await self.orders.get_item(order_id, line.purchase_order_item_id)
            if order_item is None:
                raise NotFoundError(f"Ligne de commande introuvable : {line.purchase_order_item_id}")

            remaining = order_item.quantity_ordered - order_item.quantity_received
            if line.quantity_received > remaining:
                raise ConflictError(
                    f"Quantité reçue ({line.quantity_received}) dépasse le solde restant ({remaining})."
                )

            inv_item = await self.inventory_repo.get_item_by_id(order_item.inventory_item_id)
            await self.inventory_service.receive_stock(
                item=inv_item,
                quantity=line.quantity_received,
                batch_number=line.batch_number,
                expiry_date=line.expiry_date,
                supplier_id=order.supplier_id,
                reference=order.order_number,
                created_by_id=received_by_id,
            )

            order_item.quantity_received += line.quantity_received

        await self.db.flush()

        order = await self.get_order(order_id)
        fully_received = all(i.quantity_received >= i.quantity_ordered for i in order.items)
        any_received = any(i.quantity_received > 0 for i in order.items)
        order.status = (
            PurchaseOrderStatus.RECEIVED
            if fully_received
            else PurchaseOrderStatus.PARTIALLY_RECEIVED if any_received else order.status
        )
        await self.orders.save(order)

        return await self.get_order(order_id)

    async def cancel_order(self, order_id: uuid.UUID) -> PurchaseOrder:
        order = await self.get_order(order_id)
        if order.status in (PurchaseOrderStatus.RECEIVED, PurchaseOrderStatus.PARTIALLY_RECEIVED):
            raise ConflictError("Impossible d'annuler une commande déjà (partiellement) reçue.")
        order.status = PurchaseOrderStatus.CANCELLED
        return await self.orders.save(order)

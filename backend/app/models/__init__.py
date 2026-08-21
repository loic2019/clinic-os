"""
Models package.

Every model MUST be imported here so that:
  1. Base.metadata is complete when Alembic autogenerates migrations.
  2. SQLAlchemy can resolve relationship() string references across files.
"""

from app.models.base import SoftDeleteMixin, TimestampMixin, UUIDPKMixin  # noqa: F401
from app.models.role import Permission, Role, role_permissions, user_roles  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.refresh_token import RefreshToken  # noqa: F401
from app.models.numbering import NumberingSequence  # noqa: F401
from app.models.patient import (  # noqa: F401
    BloodGroup,
    Gender,
    MedicalHistory,
    Patient,
    PatientAllergy,
    PatientContact,
    PatientInsurance,
)
from app.models.doctor import Doctor  # noqa: F401
from app.models.medical_act import MedicalAct, MedicalActPrice  # noqa: F401
from app.models.consultation import (  # noqa: F401
    Consultation,
    ConsultationAct,
    Prescription,
    PrescriptionItem,
)
from app.models.appointment import Appointment, AppointmentStatus  # noqa: F401
from app.models.laboratory import (  # noqa: F401
    LabItemStatus,
    LabOrder,
    LabOrderItem,
    LabOrderStatus,
    LabResult,
    LabSample,
    LabTestCatalog,
    SampleType,
)
from app.models.cash import CashRegister, CashRegisterSession, CashSessionStatus  # noqa: F401
from app.models.billing import (  # noqa: F401
    CancellationRequest,
    CancellationStatus,
    Invoice,
    InvoiceItem,
    InvoiceItemType,
    InvoiceStatus,
)
from app.models.payment import Payment, PaymentMethod, PaymentStatus, RefundRequest, RefundStatus  # noqa: F401
from app.models.accounting import (  # noqa: F401
    Account,
    AccountingEntry,
    AccountingLine,
    AccountType,
    Expense,
)
from app.models.inventory import (  # noqa: F401
    InventoryBatch,
    InventoryCategory,
    InventoryItem,
    InventoryMovement,
    MovementType,
)
from app.models.supplier import (  # noqa: F401
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatus,
    Supplier,
)

__all__ = [
    "UUIDPKMixin",
    "TimestampMixin",
    "SoftDeleteMixin",
    "Role",
    "Permission",
    "role_permissions",
    "user_roles",
    "User",
    "RefreshToken",
    "NumberingSequence",
    "Patient",
    "PatientContact",
    "PatientInsurance",
    "PatientAllergy",
    "MedicalHistory",
    "Gender",
    "BloodGroup",
    "Doctor",
    "MedicalAct",
    "MedicalActPrice",
    "Consultation",
    "ConsultationAct",
    "Prescription",
    "PrescriptionItem",
    "Appointment",
    "AppointmentStatus",
    "LabTestCatalog",
    "LabOrder",
    "LabOrderItem",
    "LabSample",
    "LabResult",
    "LabOrderStatus",
    "LabItemStatus",
    "SampleType",
    "CashRegister",
    "CashRegisterSession",
    "CashSessionStatus",
    "Invoice",
    "InvoiceItem",
    "InvoiceItemType",
    "InvoiceStatus",
    "CancellationRequest",
    "CancellationStatus",
    "Payment",
    "PaymentMethod",
    "PaymentStatus",
    "RefundRequest",
    "RefundStatus",
    "Account",
    "AccountingEntry",
    "AccountingLine",
    "AccountType",
    "Expense",
    "InventoryItem",
    "InventoryBatch",
    "InventoryMovement",
    "InventoryCategory",
    "MovementType",
    "Supplier",
    "PurchaseOrder",
    "PurchaseOrderItem",
    "PurchaseOrderStatus",
]

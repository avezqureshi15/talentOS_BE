from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.modules.employees.employee_model import Employee
from app.modules.forms.form_model import Form, FormStatus, FormType
from app.modules.slots.slot_model import Slot, SlotStatus

logger = get_logger(__name__)


class SlotRepositoryProtocol(Protocol):
    def create_slot(self, employee_id: int, start_at: datetime, end_at: datetime, status: str) -> Slot: ...
    def get_slot_by_id(self, slot_id: UUID) -> Slot | None: ...
    def update_slot_status(self, slot: Slot, status: str) -> Slot: ...
    def get_slots_for_employee(
        self,
        employee_id: int,
        status: str | None,
        include_past: bool,
    ) -> list[Slot]: ...
    def update_slot_times(
        self,
        slot: Slot,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        status: str | None = None,
    ) -> Slot: ...


class SlotRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_slot(self, employee_id: int, start_at, end_at, status: str = SlotStatus.AVAILABLE.value) -> Slot:
        # ``employee_id`` is a real employees.id. Callers resolve via the
        # employees directory (see slot_service.create_slots).
        slot = Slot(
            employee_id=employee_id,
            start_at=start_at,
            end_at=end_at,
            status=status,
        )
        self.db.add(slot)
        self.db.flush()
        logger.info("Created slot: id=%s | employee_id=%s", slot.id, employee_id)
        return slot

    def get_slot_by_id(self, slot_id: UUID) -> Slot | None:
        return self.db.query(Slot).filter(Slot.id == slot_id).first()

    def update_slot_status(self, slot: Slot, status: str) -> Slot:
        old_status = slot.status
        slot.status = status
        self.db.flush()
        logger.info("Updated slot status: id=%s | %s -> %s", slot.id, old_status, status)
        return slot

    def get_slots_for_employee(
        self,
        employee_id: int,
        status: str | None = None,
        include_past: bool = False,
    ) -> list[Slot]:
        # ``employee_id`` is a real employees.id — direct filter on the column.
        query = self.db.query(Slot).filter(Slot.employee_id == employee_id)
        if status is not None:
            query = query.filter(Slot.status == status)
        if not include_past:
            query = query.filter(Slot.start_at > func.now())
        return query.order_by(Slot.start_at.asc()).all()

    def update_slot_times(
        self,
        slot: Slot,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        status: str | None = None,
    ) -> Slot:
        if start_at is not None:
            slot.start_at = start_at
        if end_at is not None:
            slot.end_at = end_at
        if status is not None:
            slot.status = status
        self.db.flush()
        logger.debug("Updated slot: id=%s | start_at=%s | end_at=%s | status=%s", slot.id, slot.start_at, slot.end_at, slot.status)
        return slot

    def _slots_for_tenant(self, tenant_id: int | None):
        query = self.db.query(Slot).join(Employee, Employee.id == Slot.employee_id)
        if tenant_id is not None:
            query = query.filter(Employee.tenant_id == tenant_id)
        return query

    def get_summary(self, tenant_id: int | None) -> dict[str, int]:
        base = self._slots_for_tenant(tenant_id)
        now = func.now()

        employees_with_slots = (
            base.filter(
                Slot.status == SlotStatus.AVAILABLE.value,
                Slot.start_at > now,
                Slot.employee_id.isnot(None),
            )
            .with_entities(func.count(distinct(Slot.employee_id)))
            .scalar()
            or 0
        )
        total_available_slots = (
            base.filter(
                Slot.status == SlotStatus.AVAILABLE.value,
                Slot.start_at > now,
            )
            .count()
        )
        booked_upcoming = (
            base.filter(
                Slot.status == SlotStatus.BOOKED.value,
                Slot.start_at > now,
            )
            .count()
        )

        pending_query = (
            self.db.query(func.count(Form.id))
            .join(Employee, Employee.id == Form.employee_id)
            .filter(
                Form.type == FormType.SLOTS.value,
                Form.status == FormStatus.SENT.value,
            )
        )
        if tenant_id is not None:
            pending_query = pending_query.filter(Employee.tenant_id == tenant_id)
        pending_requests = pending_query.scalar() or 0

        return {
            "employees_with_slots": employees_with_slots,
            "total_available_slots": total_available_slots,
            "pending_requests": pending_requests,
            "booked_upcoming": booked_upcoming,
        }

from datetime import datetime
from sqlalchemy import func
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.modules.slots.slot_model import Slot, SlotStatus

logger = get_logger(__name__)


class SlotRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_slot(self, emp_id: str, start_at, end_at, status: str = SlotStatus.AVAILABLE.value) -> Slot:
        slot = Slot(emp_id=emp_id, start_at=start_at, end_at=end_at, status=status)
        self.db.add(slot)
        self.db.flush()
        logger.info("Created slot: id=%s | emp_id=%s", slot.id, emp_id)
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
        emp_id: str,
        status: str | None = None,
        include_past: bool = False,
    ) -> list[Slot]:
        query = self.db.query(Slot).filter(Slot.emp_id == emp_id)
        if status is not None:
            query = query.filter(Slot.status == status)
        if not include_past:
            query = query.filter(Slot.start_at > func.now())
        return query.order_by(Slot.start_at.asc()).all()

    def update_slot_times(
        self,
        slot: Slot,
        end_at: datetime | None = None,
        status: str | None = None,
    ) -> Slot:
        if end_at is not None:
            slot.end_at = end_at
        if status is not None:
            slot.status = status
        self.db.flush()
        logger.debug("Updated slot: id=%s | end_at=%s | status=%s", slot.id, slot.end_at, slot.status)
        return slot


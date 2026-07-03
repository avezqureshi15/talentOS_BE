from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.slots.slot_model import Schedule, Slot, SlotStatus


class SlotRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_slot(self, start_at, end_at, status: str = SlotStatus.AVAILABLE.value) -> Slot:
        slot = Slot(start_at=start_at, end_at=end_at, status=status)
        self.db.add(slot)
        self.db.flush()
        return slot

    def get_slot_by_id(self, slot_id: UUID) -> Slot | None:
        return self.db.query(Slot).filter(Slot.id == slot_id).first()

    def delete_slot(self, slot: Slot) -> None:
        self.db.delete(slot)

    def get_schedule_by_emp_id(self, emp_id: str) -> Schedule | None:
        return self.db.query(Schedule).filter(Schedule.emp_id == emp_id).first()

    def get_schedule_by_slot_id(self, slot_id: UUID) -> Schedule | None:
        return self.db.query(Schedule).filter(Schedule.slot_ids.any(slot_id)).first()

    def create_schedule(self, emp_id: str, slot_ids: list[UUID]) -> Schedule:
        schedule = Schedule(emp_id=emp_id, slot_ids=slot_ids)
        self.db.add(schedule)
        self.db.flush()
        return schedule

    def append_slot_ids(self, schedule: Schedule, new_ids: list[UUID]) -> Schedule:
        schedule.slot_ids = list(schedule.slot_ids or []) + new_ids
        self.db.flush()
        return schedule

    def remove_slot_id(self, schedule: Schedule, slot_id: UUID) -> Schedule:
        schedule.slot_ids = [sid for sid in (schedule.slot_ids or []) if sid != slot_id]
        self.db.flush()
        return schedule

    def update_slot_status(self, slot: Slot, status: str) -> Slot:
        slot.status = status
        self.db.flush()
        return slot

    def get_slots_by_ids(self, slot_ids: list[UUID], status: str | None = None) -> list[Slot]:
        """Return slots for the given ids. If status is set, filter by it; if None, return all."""
        if not slot_ids:
            return []
        query = self.db.query(Slot).filter(Slot.id.in_(slot_ids))
        if status is not None:
            query = query.filter(Slot.status == status)
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
        return slot


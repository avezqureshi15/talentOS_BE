from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import exc as sa_exc
from sqlalchemy.orm import Session

from app.common.exceptions.slot_exception import (
    EmployeeNotFoundException,
    SlotBookedException,
    SlotInvalidStatusException,
    SlotNotFoundException,
)
from app.core.logger import get_logger
from app.modules.slots.slot_model import Slot, SlotStatus
from app.modules.slots.slot_repository import SlotRepository
from app.modules.slots.slot_schema import (
    EmployeeSlotsResponse,
    SkippedSlot,
    SlotResponse,
    SlotTimeRangeCreate,
    SlotsCreateRequest,
    SlotsCreateResponse,
)
from app.modules.users.user_repository import UserRepository

logger = get_logger(__name__)

SkipReason = Literal["duplicate", "contained", "overlap", "booked_conflict"]


def _overlaps(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
    return start_a < end_b and end_a > start_b


def _contained(
    inc_start: datetime, inc_end: datetime, ex_start: datetime, ex_end: datetime
) -> bool:
    return inc_start >= ex_start and inc_end <= ex_end


def _exact_match(
    inc_start: datetime, inc_end: datetime, ex_start: datetime, ex_end: datetime
) -> bool:
    return inc_start == ex_start and inc_end == ex_end


def _same_start(inc_start: datetime, ex_start: datetime) -> bool:
    return inc_start == ex_start


_VALID_STATUS_FILTERS = {s.value for s in SlotStatus}


def _resolve_status_filter(status: str | None) -> str | None:
    """Map query param to repository filter: None = all, str = specific status."""
    if status is None:
        return SlotStatus.AVAILABLE.value
    if status == "":
        return None
    if status not in _VALID_STATUS_FILTERS:
        raise SlotInvalidStatusException(
            f"status must be one of: {', '.join(sorted(_VALID_STATUS_FILTERS))}, or empty for all"
        )
    return status


@dataclass
class _SlotAction:
    kind: Literal["skip", "update", "insert"]
    reason: SkipReason | None = None
    target: Slot | None = None
    end_at: datetime | None = None
    status: str | None = None


def _resolve_slot_action(incoming: SlotTimeRangeCreate, working_slots: list[Slot]) -> _SlotAction:
    start_at = incoming.start_at
    end_at = incoming.end_at

    for existing in working_slots:
        if existing.status == SlotStatus.BOOKED.value and _overlaps(
            start_at, end_at, existing.start_at, existing.end_at
        ):
            return _SlotAction(kind="skip", reason="booked_conflict")

    for existing in working_slots:
        if existing.status != SlotStatus.AVAILABLE.value:
            continue
        if _exact_match(start_at, end_at, existing.start_at, existing.end_at):
            return _SlotAction(kind="skip", reason="duplicate")

    for existing in working_slots:
        if existing.status != SlotStatus.INACTIVE.value:
            continue
        if _exact_match(start_at, end_at, existing.start_at, existing.end_at):
            return _SlotAction(
                kind="update",
                target=existing,
                status=SlotStatus.AVAILABLE.value,
            )

    for existing in working_slots:
        if existing.status != SlotStatus.AVAILABLE.value:
            continue
        if _same_start(start_at, existing.start_at):
            return _SlotAction(
                kind="update",
                target=existing,
                end_at=max(existing.end_at, end_at),
            )

    for existing in working_slots:
        if existing.status != SlotStatus.INACTIVE.value:
            continue
        if _same_start(start_at, existing.start_at):
            return _SlotAction(
                kind="update",
                target=existing,
                end_at=max(existing.end_at, end_at),
                status=SlotStatus.AVAILABLE.value,
            )

    for existing in working_slots:
        if existing.status != SlotStatus.AVAILABLE.value:
            continue
        if _contained(start_at, end_at, existing.start_at, existing.end_at):
            return _SlotAction(kind="skip", reason="contained")

    for existing in working_slots:
        if existing.status != SlotStatus.AVAILABLE.value:
            continue
        if _overlaps(start_at, end_at, existing.start_at, existing.end_at):
            return _SlotAction(kind="skip", reason="overlap")

    for existing in working_slots:
        if existing.status != SlotStatus.INACTIVE.value:
            continue
        if _contained(start_at, end_at, existing.start_at, existing.end_at):
            return _SlotAction(kind="insert")

    for existing in working_slots:
        if existing.status != SlotStatus.INACTIVE.value:
            continue
        if _overlaps(start_at, end_at, existing.start_at, existing.end_at):
            return _SlotAction(kind="insert")

    return _SlotAction(kind="insert")


class SlotService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = SlotRepository(db)
        self.user_repository = UserRepository(db)

    def create_slots(self, data: SlotsCreateRequest) -> SlotsCreateResponse:
        if not self.user_repository.get_by_emp_id(data.emp_id):
            raise EmployeeNotFoundException(data.emp_id)

        logger.info("Creating %d slot(s) for emp_id=%s", len(data.slots), data.emp_id)

        schedule = self.repository.get_schedule_by_emp_id(data.emp_id)
        working_slots: list[Slot] = (
            self.repository.get_slots_by_ids(list(schedule.slot_ids)) if schedule and schedule.slot_ids else []
        )

        result: list[SlotResponse] = []
        skipped: list[SkippedSlot] = []
        new_ids: list[UUID] = []

        try:
            for slot_data in data.slots:
                action = _resolve_slot_action(slot_data, working_slots)

                if action.kind == "skip":
                    assert action.reason is not None
                    skipped.append(
                        SkippedSlot(
                            start_at=slot_data.start_at,
                            end_at=slot_data.end_at,
                            reason=action.reason,
                        )
                    )
                    continue

                if action.kind == "update":
                    assert action.target is not None
                    updated = self.repository.update_slot_times(
                        action.target,
                        end_at=action.end_at,
                        status=action.status,
                    )
                    result.append(SlotResponse.model_validate(updated))
                    continue

                slot = self.repository.create_slot(
                    start_at=slot_data.start_at,
                    end_at=slot_data.end_at,
                )
                new_ids.append(slot.id)
                working_slots.append(slot)
                result.append(SlotResponse.model_validate(slot))

            if new_ids:
                if schedule:
                    self.repository.append_slot_ids(schedule, new_ids)
                else:
                    self.repository.create_schedule(data.emp_id, new_ids)

            self.db.commit()
        except sa_exc.SQLAlchemyError as exc:
            self.db.rollback()
            logger.error("Failed to create slots for emp_id=%s: %s", data.emp_id, str(exc))
            raise

        logger.info(
            "Processed %d slot(s) for emp_id=%s: %d in data, %d skipped",
            len(data.slots),
            data.emp_id,
            len(result),
            len(skipped),
        )
        return SlotsCreateResponse(data=result, skipped=skipped)

    def get_slots_for_employee(self, emp_id: str, status: str | None = None) -> EmployeeSlotsResponse:
        status_filter = _resolve_status_filter(status)
        logger.info("Fetching slots for emp_id=%s status_filter=%s", emp_id, status_filter)

        if not self.user_repository.get_by_emp_id(emp_id):
            raise EmployeeNotFoundException(emp_id)

        schedule = self.repository.get_schedule_by_emp_id(emp_id)
        if not schedule or not schedule.slot_ids:
            return EmployeeSlotsResponse(emp_id=emp_id, slots=[])

        slots = self.repository.get_slots_by_ids(list(schedule.slot_ids), status=status_filter)
        return EmployeeSlotsResponse(
            emp_id=emp_id,
            slots=[SlotResponse.model_validate(s) for s in slots],
        )

    def update_slot_status(self, slot_id: UUID, status: str) -> SlotResponse:
        logger.info("Updating slot status: id=%s status=%s", slot_id, status)

        slot = self.repository.get_slot_by_id(slot_id)
        if not slot:
            raise SlotNotFoundException(str(slot_id))

        if slot.status == SlotStatus.BOOKED.value:
            raise SlotBookedException()

        if slot.status == status:
            return SlotResponse.model_validate(slot)

        allowed = {SlotStatus.AVAILABLE.value, SlotStatus.INACTIVE.value}
        if slot.status not in allowed or status not in allowed:
            raise SlotInvalidStatusException()

        try:
            updated = self.repository.update_slot_status(slot, status)
            self.db.commit()
            self.db.refresh(updated)
        except sa_exc.SQLAlchemyError as exc:
            self.db.rollback()
            logger.error("Failed to update slot status id=%s: %s", slot_id, str(exc))
            raise

        return SlotResponse.model_validate(updated)

    def delete_slot(self, slot_id: UUID) -> None:
        logger.info("Deleting slot: id=%s", slot_id)

        slot = self.repository.get_slot_by_id(slot_id)
        if not slot:
            raise SlotNotFoundException(str(slot_id))

        if slot.status == SlotStatus.BOOKED.value:
            raise SlotBookedException("Cannot delete a booked slot")

        schedule = self.repository.get_schedule_by_slot_id(slot_id)

        try:
            if schedule:
                self.repository.remove_slot_id(schedule, slot_id)
            self.repository.delete_slot(slot)
            self.db.commit()
        except sa_exc.SQLAlchemyError as exc:
            self.db.rollback()
            logger.error("Failed to delete slot id=%s: %s", slot_id, str(exc))
            raise

        logger.info("Deleted slot: id=%s", slot_id)

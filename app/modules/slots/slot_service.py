from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from sqlalchemy import exc as sa_exc
from sqlalchemy.orm import Session

from app.common.exceptions.slot_exception import (
    EmployeeNotFoundException,
)
from app.core.logger import get_logger
from app.modules.forms.form_service import FormService
from app.modules.slots.slot_model import Slot, SlotStatus
from app.modules.slots.slot_presenter import now_ist, present_slot_item, to_ist
from app.modules.slots.slot_repository import SlotRepository
from app.modules.slots.slot_schema import (
    BatchEmployeeSlotsResponse,
    EmployeeSlotsResponse,
    SkippedSlot,
    SlotResponse,
    SlotListItemResponse,
    SlotTimeRangeCreate,
    SlotsCreateRequest,
    SlotsCreateResponse,
)
from app.modules.users.user_repository import UserRepository

logger = get_logger(__name__)

SkipReason = Literal["duplicate", "contained", "overlap", "booked_conflict", "not_in_future"]


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
        self.form_service = FormService(db)

    def create_slots(self, data: SlotsCreateRequest) -> SlotsCreateResponse:
        if not self.user_repository.get_by_emp_id(data.emp_id):
            raise EmployeeNotFoundException(data.emp_id)

        logger.info("Creating %d slot(s) for emp_id=%s", len(data.slots), data.emp_id)

        working_slots: list[Slot] = self.repository.get_slots_for_employee(
            data.emp_id,
            status=None,
            include_past=True,
        )

        result: list[SlotResponse] = []
        skipped: list[SkippedSlot] = []

        try:
            current_ist = now_ist()
            for slot_data in data.slots:
                if to_ist(slot_data.start_at) <= current_ist:
                    skipped.append(
                        SkippedSlot(
                            start_at=slot_data.start_at,
                            end_at=slot_data.end_at,
                            reason="not_in_future",
                        )
                    )
                    continue

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
                    emp_id=data.emp_id,
                    start_at=slot_data.start_at,
                    end_at=slot_data.end_at,
                )
                working_slots.append(slot)
                result.append(SlotResponse.model_validate(slot))

            self.db.commit()
            self.form_service.mark_slots_form_submitted(data.emp_id)
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

    def get_slots_for_employees(self, emp_ids: list[str]) -> BatchEmployeeSlotsResponse:
        data: list[EmployeeSlotsResponse] = []
        for emp_id in emp_ids:
            if not self.user_repository.get_by_emp_id(emp_id):
                data.append(EmployeeSlotsResponse(emp_id=emp_id, slots=[]))
                continue
            slots = self.repository.get_slots_for_employee(
                emp_id,
                status=SlotStatus.AVAILABLE.value,
                include_past=False,
            )
            data.append(
                EmployeeSlotsResponse(
                    emp_id=emp_id,
                    slots=[
                        SlotListItemResponse.model_validate(present_slot_item(s).__dict__)
                        for s in slots
                    ],
                )
            )
        return BatchEmployeeSlotsResponse(data=data)

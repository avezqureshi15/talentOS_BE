from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.modules.slots.slot_model import Slot, SlotStatus
from app.modules.slots.slot_schema import SlotTimeRangeCreate

SkipReason = Literal["duplicate", "contained", "overlap", "booked_conflict", "not_in_future"]


def _overlaps(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
    return start_a < end_b and end_a > start_b


def _exact_match(
    inc_start: datetime, inc_end: datetime, ex_start: datetime, ex_end: datetime
) -> bool:
    return inc_start == ex_start and inc_end == ex_end


@dataclass
class _SlotAction:
    kind: Literal["skip", "update", "insert"]
    reason: SkipReason | None = None
    target: Slot | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    status: str | None = None


def _union_update(existing: Slot, start_at: datetime, end_at: datetime) -> _SlotAction:
    """Union the incoming range into the existing slot instead of dropping it.

    Keeps custom slots provided through the booking form: the existing slot's
    start/end are widened so the custom range is fully covered.
    """
    return _SlotAction(
        kind="update",
        target=existing,
        start_at=min(start_at, existing.start_at),
        end_at=max(end_at, existing.end_at),
    )


def resolve_slot_action(incoming: SlotTimeRangeCreate, working_slots: list[Slot]) -> _SlotAction:
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
        if _overlaps(start_at, end_at, existing.start_at, existing.end_at):
            return _union_update(existing, start_at, end_at)

    for existing in working_slots:
        if existing.status != SlotStatus.INACTIVE.value:
            continue
        if _overlaps(start_at, end_at, existing.start_at, existing.end_at):
            return _SlotAction(
                kind="update",
                target=existing,
                start_at=min(start_at, existing.start_at),
                end_at=max(end_at, existing.end_at),
                status=SlotStatus.AVAILABLE.value,
            )

    return _SlotAction(kind="insert")

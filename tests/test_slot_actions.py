from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.modules.slots.slot_actions import resolve_slot_action
from app.modules.slots.slot_model import Slot, SlotStatus
from app.modules.slots.slot_schema import SlotTimeRangeCreate

_T0 = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
_SLOT_ID = UUID("00000000-0000-0000-0000-000000000001")


def _existing(start: datetime, end: datetime, status: str = SlotStatus.AVAILABLE.value) -> Slot:
    return Slot(
        id=_SLOT_ID,
        employee_id=1,
        start_at=start,
        end_at=end,
        status=status,
    )


def _incoming(start: datetime, end: datetime) -> SlotTimeRangeCreate:
    return SlotTimeRangeCreate(start_at=start, end_at=end)


def _t(hour: int, minute: int = 0) -> datetime:
    return _T0.replace(hour=hour, minute=minute)


def test_exact_duplicate_is_skipped():
    existing = _existing(_t(9), _t(9, 30))
    action = resolve_slot_action(_incoming(_t(9), _t(9, 30)), [existing])
    assert action.kind == "skip"
    assert action.reason == "duplicate"


def test_same_start_custom_slot_extends_existing():
    existing = _existing(_t(9), _t(9, 30))
    action = resolve_slot_action(_incoming(_t(9), _t(10)), [existing])
    assert action.kind == "update"
    assert action.target is existing
    assert action.start_at == _t(9)
    assert action.end_at == _t(10)


def test_custom_slot_fully_inside_existing_is_covered_by_union():
    existing = _existing(_t(9), _t(10))
    action = resolve_slot_action(_incoming(_t(9, 15), _t(9, 45)), [existing])
    assert action.kind == "update"
    assert action.start_at == _t(9)
    assert action.end_at == _t(10)


def test_partial_overlap_extends_end():
    existing = _existing(_t(10), _t(10, 30))
    action = resolve_slot_action(_incoming(_t(10, 15), _t(11)), [existing])
    assert action.kind == "update"
    assert action.start_at == _t(10)
    assert action.end_at == _t(11)


def test_overlap_starting_before_existing_widens_start():
    existing = _existing(_t(10), _t(10, 30))
    action = resolve_slot_action(_incoming(_t(9, 45), _t(10, 15)), [existing])
    assert action.kind == "update"
    assert action.start_at == _t(9, 45)
    assert action.end_at == _t(10, 30)


def test_custom_slot_containing_existing_unions_both_sides():
    existing = _existing(_t(10), _t(10, 30))
    action = resolve_slot_action(_incoming(_t(9, 30), _t(11)), [existing])
    assert action.kind == "update"
    assert action.start_at == _t(9, 30)
    assert action.end_at == _t(11)


def test_booked_conflict_is_skipped():
    existing = _existing(_t(10), _t(11), status=SlotStatus.BOOKED.value)
    action = resolve_slot_action(_incoming(_t(10, 30), _t(11, 30)), [existing])
    assert action.kind == "skip"
    assert action.reason == "booked_conflict"


def test_no_overlap_inserts():
    existing = _existing(_t(9), _t(10))
    action = resolve_slot_action(_incoming(_t(11), _t(12)), [existing])
    assert action.kind == "insert"
    assert action.target is None


def test_inactive_exact_match_reactivates():
    existing = _existing(_t(9), _t(9, 30), status=SlotStatus.INACTIVE.value)
    action = resolve_slot_action(_incoming(_t(9), _t(9, 30)), [existing])
    assert action.kind == "update"
    assert action.target is existing
    assert action.status == SlotStatus.AVAILABLE.value


def test_inactive_overlap_reactivates_with_union():
    existing = _existing(_t(9), _t(10), status=SlotStatus.INACTIVE.value)
    action = resolve_slot_action(_incoming(_t(9, 30), _t(11)), [existing])
    assert action.kind == "update"
    assert action.target is existing
    assert action.status == SlotStatus.AVAILABLE.value
    assert action.start_at == _t(9)
    assert action.end_at == _t(11)


def test_adjacent_touching_ranges_do_not_overlap():
    existing = _existing(_t(9), _t(10))
    action = resolve_slot_action(_incoming(_t(10), _t(11)), [existing])
    assert action.kind == "insert"

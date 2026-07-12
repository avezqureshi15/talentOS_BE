from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.modules.slots.slot_model import Slot
from app.modules.slots.slot_schema import SlotListItemResponse

IST = ZoneInfo("Asia/Kolkata")


def to_ist(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST)


def format_slot_label_ist(start_at: datetime, end_at: datetime) -> str:
    start = to_ist(start_at)
    end = to_ist(end_at)
    return f"{start.strftime('%I:%M %p')} - {end.strftime('%I:%M %p')}"


def now_ist() -> datetime:
    return datetime.now(IST)


def format_slot_day_ist(start_at: datetime, now_ist_dt: datetime | None = None) -> str:
    start = to_ist(start_at)
    now = now_ist_dt or now_ist()
    if start.date() == now.date():
        return "Today"
    if start.date() == (now.date() + timedelta(days=1)):
        return "Tomorrow"
    return start.strftime("%d %b")


def present_slot_item(slot: Slot, now_ist_dt: datetime | None = None) -> SlotListItemResponse:
    return SlotListItemResponse(
        id=str(slot.id),
        label=format_slot_label_ist(slot.start_at, slot.end_at),
        day=format_slot_day_ist(slot.start_at, now_ist_dt),
    )

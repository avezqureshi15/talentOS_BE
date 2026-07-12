from pydantic import BaseModel


class CalendarEventResponse(BaseModel):
    event_id: str
    meet_link: str | None = None
    calendar_link: str = ""

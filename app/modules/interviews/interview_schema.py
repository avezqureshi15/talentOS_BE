from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, model_validator


class ScheduleMeetRequest(BaseModel):
    title: str = Field(..., min_length=1)
    start: datetime
    end: datetime
    attendees: list[EmailStr] = Field(..., min_length=1)
    description: str = ""

    @model_validator(mode="after")
    def validate_range(self) -> "ScheduleMeetRequest":
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self


class ScheduleMeetResponse(BaseModel):
    event_id: str
    meet_link: str | None = None
    calendar_link: str

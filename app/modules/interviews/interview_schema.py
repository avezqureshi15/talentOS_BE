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


class ReviewCreate(BaseModel):
    round_id: str
    employee_id: int | None = None
    entity_type: str
    reviews: dict | None = None
    verdict: str | None = None


class ReviewResponse(BaseModel):
    id: str
    round_id: str
    employee_id: int | None = None
    entity_type: str
    reviews: dict | None = None
    verdict: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class InterviewCreate(BaseModel):
    round_id: str
    interviewer_id: int
    slot_id: str | None = None
    start_time: datetime
    end_time: datetime
    status: str = "SCHEDULED"


class InterviewResponse(BaseModel):
    id: str
    round_id: str
    interviewer_id: int
    slot_id: str | None = None
    event_id: str | None = None
    start_time: datetime
    end_time: datetime
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InterviewStatusUpdate(BaseModel):
    status: str
    event_id: str | None = None

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ScheduleMeetRequest(BaseModel):
    title: str
    start: datetime
    end: datetime
    attendees: list[str]
    description: str | None = None


class ScheduleMeetResponse(BaseModel):
    event_id: str | None = None
    html_link: str | None = None
    start: datetime | None = None
    end: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class InterviewCreate(BaseModel):
    round_id: str
    interviewer_id: int
    start_time: datetime
    end_time: datetime
    event_id: str | None = None
    status: str = "scheduled"


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

    model_config = ConfigDict(from_attributes=True)


class InterviewStatusUpdate(BaseModel):
    status: str
    event_id: str | None = None


# ── List interviews DTOs ───────────────────────────────────

class PositionBrief(BaseModel):
    id: str
    title: str


class InterviewerBrief(BaseModel):
    id: str
    name: str
    email: str


class CandidateBrief(BaseModel):
    id: str
    name: str | None = None
    email: str | None = None


class ScheduleBrief(BaseModel):
    start_time: datetime
    end_time: datetime
    timezone: str = "UTC"


class MeetingBrief(BaseModel):
    platform: str | None = None
    url: str | None = None


class InterviewListItem(BaseModel):
    id: str
    status: str
    position: PositionBrief
    interviewer: InterviewerBrief
    candidate: CandidateBrief
    schedule: ScheduleBrief
    meeting: MeetingBrief


class InterviewPagination(BaseModel):
    current_page: int
    per_page: int
    total_records: int
    has_more: bool


class InterviewsData(BaseModel):
    interviews: list[InterviewListItem]
    pagination: InterviewPagination


class InterviewListResponse(BaseModel):
    success: bool = True
    data: InterviewsData

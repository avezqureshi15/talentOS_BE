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
    meet_link: str | None = None
    html_link: str | None = None
    start: datetime | None = None
    end: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class InterviewCreate(BaseModel):
    round_id: str
    event_id: str | None = None
    status: str = "scheduled"


class InterviewResponse(BaseModel):
    id: str
    round_id: str
    slot_id: str | None = None
    event_id: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InterviewStatusUpdate(BaseModel):
    status: str
    event_id: str | None = None


# ── Scheduling DTOs ──────────────────────────────────────

class ScheduleInterviewRequest(BaseModel):
    round_id: str
    slot_id: str


class ScheduleInterviewResponse(BaseModel):
    id: str
    round_id: str
    slot_id: str | None = None
    event_id: str | None = None
    meet_link: str | None = None
    status: str

    model_config = ConfigDict(from_attributes=True)


class RescheduleInterviewRequest(BaseModel):
    slot_id: str
    interviewer_ids: list[int] | None = None


class BookInterviewRequest(BaseModel):
    round_name: str
    slot_id: str
    jd_id: str
    candidate_id: int
    interviewer_ids: list[int]
    create_google_meet: bool = True


class CancelInterviewResponse(BaseModel):
    id: str
    status: str

    model_config = ConfigDict(from_attributes=True)

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
    interview_status: str | None = None
    round_name: str
    cancelled_at: str | None = None
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

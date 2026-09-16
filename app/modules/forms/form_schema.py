from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

class AskFormRequest(BaseModel):
    emp_ids: list[str] = Field(..., min_length=1)
    type: Literal["SLOTS", "REVIEW"] = "SLOTS"
    round_id: UUID | None = None
    candidate_id: int | None = None
    requester_name: str | None = Field(default=None, max_length=255)


class AskFormResultItem(BaseModel):
    emp_id: str
    status: Literal["SUCCESS", "FAILED"]
    message: str


class AskFormResponse(BaseModel):
    message: str
    results: list[AskFormResultItem]


class SubmittedSlotItem(BaseModel):
    start_at: datetime
    end_at: datetime


class SubmittedReviewPayload(BaseModel):
    reviews: dict | None = None
    verdict: str | None = None


class FormValidateResponse(BaseModel):
    valid: bool
    reason: str
    emp_id: str | None = None
    type: str | None = None
    round_id: UUID | None = None
    candidate_id: int | None = None
    hiring_request_id: UUID | None = None
    review_questions: dict | None = None
    read_only: bool = False
    submitted_slots: list[SubmittedSlotItem] | None = None
    submitted_review: SubmittedReviewPayload | None = None


class PendingMailTask(BaseModel):
    user_id: int
    form_id: UUID


class NotifyFormRequest(BaseModel):
    user_id: int
    type: Literal["SLOTS", "REVIEW"] = "SLOTS"
    reminder: bool = True
    requester_name: str | None = Field(default=None, max_length=255)


class NotifyFormResponse(BaseModel):
    message: str
    detail: str
    form_id: UUID


class FormSubmitResponse(BaseModel):
    message: str


class PendingSlotFormItem(BaseModel):
    form_id: UUID
    emp_id: str
    name: str
    email: str
    last_sent_at: datetime
    reminded_at: datetime | None
    days_waiting: int


class PaginatedPendingSlotFormsResponse(BaseModel):
    data: list[PendingSlotFormItem]
    total: int
    page: int
    per_page: int
    has_more: bool

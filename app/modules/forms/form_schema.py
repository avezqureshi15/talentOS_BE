from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class AskFormRequest(BaseModel):
    emp_ids: list[str] = Field(..., min_length=1)
    type: Literal["SLOTS", "REVIEW"] = "SLOTS"
    round_id: UUID | None = None
    candidate_id: int | None = None


class AskFormResultItem(BaseModel):
    emp_id: str
    status: Literal["SUCCESS", "FAILED"]
    message: str


class AskFormResponse(BaseModel):
    message: str
    results: list[AskFormResultItem]


class FormValidateResponse(BaseModel):
    valid: bool
    reason: str
    emp_id: str | None = None
    type: str | None = None
    round_id: UUID | None = None
    candidate_id: int | None = None


class PendingMailTask(BaseModel):
    emp_id: str
    form_id: UUID


class FormSubmitResponse(BaseModel):
    message: str

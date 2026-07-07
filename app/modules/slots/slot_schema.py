from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SlotTimeRangeCreate(BaseModel):
    start_at: datetime
    end_at: datetime

    @model_validator(mode="after")
    def validate_range(self) -> "SlotTimeRangeCreate":
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")
        return self


class SlotsCreateRequest(BaseModel):
    emp_id: str = Field(..., min_length=1, max_length=50)
    slots: list[SlotTimeRangeCreate] = Field(..., min_length=1)


class SlotStatusUpdate(BaseModel):
    status: Literal["available", "inactive"]


class SlotResponse(BaseModel):
    id: UUID
    start_at: datetime
    end_at: datetime
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SkippedSlot(BaseModel):
    start_at: datetime
    end_at: datetime
    reason: Literal["duplicate", "contained", "overlap", "booked_conflict", "not_in_future"]


class SlotsCreateResponse(BaseModel):
    data: list[SlotResponse]
    skipped: list[SkippedSlot] = Field(default_factory=list)


class SlotListItemResponse(BaseModel):
    id: str
    label: str
    day: str


class EmployeeSlotsResponse(BaseModel):
    emp_id: str
    slots: list[SlotListItemResponse]


class BatchEmployeeSlotsResponse(BaseModel):
    data: list[EmployeeSlotsResponse]

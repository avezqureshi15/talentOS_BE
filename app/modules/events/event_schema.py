import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EventCreate(BaseModel):
    entity_type: str
    entity_id: str
    job_id: uuid.UUID | None = None
    candidate_id: int | None = None
    event_name: str
    state_code: str
    actor_type: str | None = None
    actor_id: str | None = None
    remark: str | None = None
    action_url: str | None = None
    action_label: str | None = None
    event_metadata: dict | None = None


class EventUpdate(BaseModel):
    entity_type: str | None = None
    entity_id: str | None = None
    job_id: uuid.UUID | None = None
    candidate_id: int | None = None
    event_name: str | None = None
    state_code: str | None = None
    actor_type: str | None = None
    actor_id: str | None = None
    remark: str | None = None
    action_url: str | None = None
    action_label: str | None = None
    event_metadata: dict | None = None


class EventResponse(BaseModel):
    id: uuid.UUID
    entity_type: str
    entity_id: str
    job_id: uuid.UUID | None = None
    candidate_id: int | None = None
    event_name: str
    state_code: str
    actor_type: str | None = None
    actor_id: str | None = None
    remark: str | None = None
    action_url: str | None = None
    action_label: str | None = None
    event_metadata: dict | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

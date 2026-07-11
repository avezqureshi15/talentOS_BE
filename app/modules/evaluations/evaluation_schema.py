from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from typing import Annotated


class WebhookRecord(BaseModel):
    """The `record` object inside a Supabase database webhook payload
    for an INSERT on the `job_applications` table."""

    id: int | str = Field(...)
    job_id: str = Field(...)
    name: str | None = Field(None)
    email: str | None = Field(None)
    phone: str | None = Field(None)
    cover_letter: str | None = Field(None)
    resume_url: str | None = Field(None)
    current_ctc: str | None = Field(None)
    expected_ctc: str | None = Field(None)
    location: str | None = Field(None)
    years_of_experience: str | None = Field(None)
    notice_period: str | None = Field(None)
    how_did_you_hear: str | None = Field(None)
    linkedin_url: str | None = Field(None)
    willing_to_relocate: bool = False
    status: str | None = Field(None)
    created_at: datetime | None = Field(None)

    model_config = ConfigDict(extra="ignore")


class SupabaseWebhookPayload(BaseModel):
    """Fixed envelope Supabase sends to database webhooks."""

    type: str = Field(...)
    table: str = Field(...)
    schema_name: str | None = Field(None, alias="schema")
    record: WebhookRecord = Field(...)
    old_record: WebhookRecord | None = Field(None)

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class IngestResponse(BaseModel):
    status: str
    application_id: str
    detail: str | None = None


class EvaluationMessage(BaseModel):
    """Payload published to the Kafka evaluation topic. Kept small and flat."""

    application_id: str
    job_id: str
    resume_url: str | None = None
    candidate_name: str | None = None
    candidate_email: str | None = None
    enqueued_at: str


class EvaluationResponse(BaseModel):
    id: int
    application_id: Annotated[str, Field(validation_alias="external_application_id")]
    job_id: Annotated[str, Field(validation_alias="external_job_id")]
    candidate_name: str | None
    candidate_email: str | None
    resume_url: str | None
    status: str
    fit_score: int | None
    summary_md: str | None
    ats_threshold_used: int | None
    attempts: int
    error_reason: str | None
    current_round_id: str | None
    final_verdict: str | None
    created_at: datetime
    updated_at: datetime
    evaluated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)

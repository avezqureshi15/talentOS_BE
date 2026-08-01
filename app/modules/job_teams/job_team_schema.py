import uuid

from pydantic import BaseModel, ConfigDict, Field


class JobTeamMemberResponse(BaseModel):
    user_id: int
    name: str
    email: str
    is_owner: bool
    role: str

    model_config = ConfigDict(from_attributes=True)


class JobTeamResponse(BaseModel):
    hiring_request_id: uuid.UUID
    data: list[JobTeamMemberResponse]
    total: int


class AddTeamMemberRequest(BaseModel):
    user_id: int
    is_owner: bool = False
    role: str | None = Field(None, description="job_owner | recruiter | reviewer; defaults to recruiter")


class UpdateTeamMemberRequest(BaseModel):
    is_owner: bool | None = None
    role: str | None = Field(None, description="job_owner | recruiter | reviewer")

import uuid

from pydantic import BaseModel, ConfigDict, Field


class JobTeamMemberResponse(BaseModel):
    user_id: int
    name: str
    email: str
    designation: str | None = None
    is_owner: bool
    role: str = Field(..., description="The member's global org role (superadmin | account_admin | job_owner | reviewer)")

    model_config = ConfigDict(from_attributes=True)


class JobTeamResponse(BaseModel):
    hiring_request_id: uuid.UUID
    data: list[JobTeamMemberResponse]
    total: int


class AddTeamMemberRequest(BaseModel):
    user_id: int
    is_owner: bool = False


class UpdateTeamMemberRequest(BaseModel):
    is_owner: bool | None = None

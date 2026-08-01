import uuid

from pydantic import BaseModel, ConfigDict


class JobTeamMemberResponse(BaseModel):
    user_id: int
    name: str
    email: str
    is_owner: bool

    model_config = ConfigDict(from_attributes=True)


class JobTeamResponse(BaseModel):
    hiring_request_id: uuid.UUID
    data: list[JobTeamMemberResponse]
    total: int


class AddTeamMemberRequest(BaseModel):
    user_id: int
    is_owner: bool = False


class UpdateTeamMemberRequest(BaseModel):
    is_owner: bool

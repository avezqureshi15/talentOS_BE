from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.authorization import require_permission
from app.core.config import settings
from app.core.permissions import Permission
from app.db.session import get_db
from app.modules.job_teams.job_team_schema import (
    AddTeamMemberRequest,
    JobTeamResponse,
    UpdateTeamMemberRequest,
)
from app.modules.job_teams.job_team_service import JobTeamService

router = APIRouter(
    prefix=f"{settings.API_V1_PREFIX}/hiring-requests/{{hiring_request_id}}/team",
    tags=["job-teams"],
)


@router.get("", response_model=JobTeamResponse)
def list_team_members(
    hiring_request_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission(Permission.APPLICATION_VIEW)),
):
    return JobTeamService(db).list_members(hiring_request_id)


@router.post("", response_model=JobTeamResponse, status_code=201)
def add_team_member(
    hiring_request_id: UUID,
    body: AddTeamMemberRequest,
    db: Session = Depends(get_db),
    _=Depends(require_permission(Permission.JOB_TEAM_MANAGE)),
):
    return JobTeamService(db).add_member(hiring_request_id, body)


@router.patch("/{user_id}", response_model=JobTeamResponse)
def update_team_member(
    hiring_request_id: UUID,
    user_id: int,
    body: UpdateTeamMemberRequest,
    db: Session = Depends(get_db),
    _=Depends(require_permission(Permission.JOB_TEAM_MANAGE)),
):
    return JobTeamService(db).update_member(hiring_request_id, user_id, body)


@router.delete("/{user_id}", response_model=JobTeamResponse)
def remove_team_member(
    hiring_request_id: UUID,
    user_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_permission(Permission.JOB_TEAM_MANAGE)),
):
    return JobTeamService(db).remove_member(hiring_request_id, user_id)

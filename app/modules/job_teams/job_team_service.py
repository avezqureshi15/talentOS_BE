import uuid

from sqlalchemy.orm import Session

from app.common.exceptions.hiring_request_exception import HiringRequestNotFoundException
from app.common.exceptions.job_team_exception import (
    JobTeamAlreadyMemberException,
    JobTeamMemberNotFoundException,
)
from app.core.logger import get_logger
from app.modules.hiring_requests.hiring_request_model import HiringRequest
from app.modules.job_teams.job_team_model import JobTeamMember
from app.modules.job_teams.job_team_repository import JobTeamRepository
from app.modules.job_teams.job_team_schema import (
    AddTeamMemberRequest,
    JobTeamMemberResponse,
    JobTeamResponse,
    UpdateTeamMemberRequest,
)
from app.modules.users.user_model import User

logger = get_logger(__name__)


class JobTeamService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = JobTeamRepository(db)

    def _get_hiring_request_or_raise(self, hiring_request_id: uuid.UUID) -> HiringRequest:
        hr = self.db.query(HiringRequest).filter(HiringRequest.id == hiring_request_id).first()
        if not hr:
            raise HiringRequestNotFoundException(hiring_request_id)
        return hr

    def list_members(self, hiring_request_id: uuid.UUID) -> JobTeamResponse:
        self._get_hiring_request_or_raise(hiring_request_id)
        rows = self.repo.list_members(hiring_request_id)
        data = [
            JobTeamMemberResponse(
                user_id=user.id,
                name=user.name,
                email=user.email,
                is_owner=member.is_owner,
            )
            for member, user in rows
        ]
        return JobTeamResponse(
            hiring_request_id=hiring_request_id,
            data=data,
            total=len(data),
        )

    def add_member(self, hiring_request_id: uuid.UUID, body: AddTeamMemberRequest) -> JobTeamResponse:
        self._get_hiring_request_or_raise(hiring_request_id)
        if self.repo.get_member(hiring_request_id, body.user_id):
            raise JobTeamAlreadyMemberException(body.user_id)

        user = self.db.query(User).filter(User.id == body.user_id).first()
        if not user:
            from app.common.exceptions.user_exception import UserNotFoundException

            raise UserNotFoundException(body.user_id)

        self.repo.add_member(hiring_request_id, body.user_id, is_owner=body.is_owner)
        logger.info(
            "Job team member added: hiring_request_id=%s user_id=%d is_owner=%s",
            hiring_request_id, body.user_id, body.is_owner,
        )
        return self.list_members(hiring_request_id)

    def update_member(self, hiring_request_id: uuid.UUID, user_id: int, body: UpdateTeamMemberRequest) -> JobTeamResponse:
        self._get_hiring_request_or_raise(hiring_request_id)
        if not self.repo.get_member(hiring_request_id, user_id):
            raise JobTeamMemberNotFoundException(user_id)

        self.repo.set_owner(hiring_request_id, user_id, body.is_owner)
        logger.info(
            "Job team member updated: hiring_request_id=%s user_id=%d is_owner=%s",
            hiring_request_id, user_id, body.is_owner,
        )
        return self.list_members(hiring_request_id)

    def remove_member(self, hiring_request_id: uuid.UUID, user_id: int) -> JobTeamResponse:
        self._get_hiring_request_or_raise(hiring_request_id)
        if not self.repo.get_member(hiring_request_id, user_id):
            raise JobTeamMemberNotFoundException(user_id)

        self.repo.remove_member(hiring_request_id, user_id)
        logger.info("Job team member removed: hiring_request_id=%s user_id=%d", hiring_request_id, user_id)
        return self.list_members(hiring_request_id)

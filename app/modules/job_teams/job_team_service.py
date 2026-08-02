import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.common.exceptions.hiring_request_exception import HiringRequestNotFoundException
from app.common.exceptions.job_team_exception import (
    JobTeamAlreadyMemberException,
    JobTeamMemberNotFoundException,
)
from app.core.logger import get_logger
from app.modules.auth.auth_schema import UserInfo
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

    def _assert_same_tenant(self, hr: HiringRequest, user: User) -> None:
        if hr.tenant_id is not None and user.tenant_id != hr.tenant_id:
            raise HTTPException(
                status_code=403,
                detail="Cannot add a user from another tenant to this job's team",
            )

    def _assert_owner_assignment_allowed(self, current_user: UserInfo) -> None:
        if current_user.role not in ("superadmin", "account_admin"):
            raise HTTPException(
                status_code=403,
                detail="Only account admins can mark a user as Job Owner",
            )

    def list_members(self, hiring_request_id: uuid.UUID) -> JobTeamResponse:
        self._get_hiring_request_or_raise(hiring_request_id)
        rows = self.repo.list_members(hiring_request_id)
        data = [
            JobTeamMemberResponse(
                user_id=user.id,
                name=user.name,
                email=user.email,
                is_owner=member.is_owner,
                role=user.role,
            )
            for member, user in rows
        ]
        return JobTeamResponse(
            hiring_request_id=hiring_request_id,
            data=data,
            total=len(data),
        )

    def add_member(
        self,
        hiring_request_id: uuid.UUID,
        body: AddTeamMemberRequest,
        current_user: UserInfo,
    ) -> JobTeamResponse:
        hr = self._get_hiring_request_or_raise(hiring_request_id)
        if self.repo.get_member(hiring_request_id, body.user_id):
            raise JobTeamAlreadyMemberException(body.user_id)

        user = self.db.query(User).filter(User.id == body.user_id).first()
        if not user:
            from app.common.exceptions.user_exception import UserNotFoundException

            raise UserNotFoundException(body.user_id)

        self._assert_same_tenant(hr, user)
        if body.is_owner:
            self._assert_owner_assignment_allowed(current_user)

        self.repo.add_member(hiring_request_id, body.user_id, is_owner=body.is_owner)
        self._notify_job_assignment(
            body.user_id, hiring_request_id, hr.title, "job_owner" if body.is_owner else "recruiter"
        )
        logger.info(
            "Job team member added: hiring_request_id=%s user_id=%d is_owner=%s",
            hiring_request_id, body.user_id, body.is_owner,
        )
        return self.list_members(hiring_request_id)

    def _notify_job_assignment(
        self, user_id: int, hiring_request_id: uuid.UUID, job_title: str, role: str,
    ) -> None:
        from app.modules.notifications.notification_model import NotificationType
        from app.modules.notifications.notification_service import NotificationService

        NotificationService(self.db).notify(
            employee_id=user_id,
            notification_type=NotificationType.JOB_ASSIGNED.value,
            title=f"Assigned to {job_title or 'a job'}",
            body=f"You were added to the team as {role}.",
            action_url=f"/hiring-requests/{hiring_request_id}",
            action_label="View job",
            job_id=hiring_request_id,
            dedupe_key=f"JOB_ASSIGNED-{hiring_request_id}",
        )
        self.db.commit()

    def update_member(
        self,
        hiring_request_id: uuid.UUID,
        user_id: int,
        body: UpdateTeamMemberRequest,
        current_user: UserInfo,
    ) -> JobTeamResponse:
        self._get_hiring_request_or_raise(hiring_request_id)
        member = self.repo.get_member(hiring_request_id, user_id)
        if not member:
            raise JobTeamMemberNotFoundException(user_id)

        if body.is_owner is not None:
            self._assert_owner_assignment_allowed(current_user)

        self.repo.update_member(
            hiring_request_id,
            user_id,
            is_owner=body.is_owner,
        )
        if body.role is not None or body.is_owner is not None:
            hr = self._get_hiring_request_or_raise(hiring_request_id)
            final_role = body.role
            if body.is_owner is True or body.role == "job_owner":
                final_role = "job_owner"
            self._notify_job_assignment(user_id, hiring_request_id, hr.title, final_role or member.role)
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

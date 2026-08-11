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
from app.modules.employees.employee_model import Employee
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
    """Team-membership operations. ``body.user_id`` and route ``user_id``
    params are semantically ``employees.id`` post the employees cutover —
    the FE picker sources them from ``/employees/``. The field names on
    the wire are kept for backward compatibility."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = JobTeamRepository(db)

    def _get_hiring_request_or_raise(self, hiring_request_id: uuid.UUID) -> HiringRequest:
        hr = self.db.query(HiringRequest).filter(HiringRequest.id == hiring_request_id).first()
        if not hr:
            raise HiringRequestNotFoundException(hiring_request_id)
        return hr

    def _get_employee_or_raise(self, employee_id: int) -> Employee:
        employee = self.db.query(Employee).filter(Employee.id == employee_id).first()
        if not employee:
            from app.common.exceptions.user_exception import UserNotFoundException
            raise UserNotFoundException(employee_id)
        return employee

    def _assert_same_tenant(self, hr: HiringRequest, employee: Employee) -> None:
        if hr.tenant_id is not None and employee.tenant_id != hr.tenant_id:
            raise HTTPException(
                status_code=403,
                detail="Cannot add an employee from another tenant to this job's team",
            )

    def _assert_owner_assignment_allowed(self, current_user: UserInfo) -> None:
        if current_user.role not in ("superadmin", "account_admin"):
            raise HTTPException(
                status_code=403,
                detail="Only account admins can mark a user as Job Owner",
            )

    def _resolve_user_id(self, employee_id: int) -> int | None:
        """Reverse-lookup the linked user for notifications. Returns None
        for HR-only employees (no login) — those can't receive notifications."""
        return self.db.query(User.id).filter(User.employee_id == employee_id).scalar()

    def list_members(self, hiring_request_id: uuid.UUID) -> JobTeamResponse:
        self._get_hiring_request_or_raise(hiring_request_id)
        rows = self.repo.list_members(hiring_request_id)
        data = [
            JobTeamMemberResponse(
                user_id=member.employee_id,
                name=user.name,
                email=user.email,
                designation=user.employee.designation if user.employee else None,
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
        employee_id = body.user_id  # wire-name legacy; value is employees.id
        if self.repo.get_member(hiring_request_id, employee_id):
            raise JobTeamAlreadyMemberException(employee_id)

        employee = self._get_employee_or_raise(employee_id)
        self._assert_same_tenant(hr, employee)

        linked_user = (
            self.db.query(User)
            .filter(User.employee_id == employee_id, User.is_active == True)
            .first()
        )
        if linked_user is None or not linked_user.role:
            raise HTTPException(
                status_code=422,
                detail="Cannot assign job to a user without an active, role-bearing account",
            )

        if body.is_owner:
            self._assert_owner_assignment_allowed(current_user)

        self.repo.add_member(hiring_request_id, employee_id, is_owner=body.is_owner)
        self._notify_job_assignment(
            employee_id, hiring_request_id, hr.title, "job_owner" if body.is_owner else "recruiter"
        )
        logger.info(
            "Job team member added: hiring_request_id=%s employee_id=%d is_owner=%s",
            hiring_request_id, employee_id, body.is_owner,
        )
        return self.list_members(hiring_request_id)

    def _notify_job_assignment(
        self, employee_id: int, hiring_request_id: uuid.UUID, job_title: str, role: str,
    ) -> None:
        from app.modules.notifications.notification_model import NotificationType
        from app.modules.notifications.notification_service import NotificationService

        user_id = self._resolve_user_id(employee_id)
        if user_id is None:
            # HR-only employee (no linked login) — nothing to notify.
            return
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
        user_id: int,  # wire-name legacy; value is employees.id
        body: UpdateTeamMemberRequest,
        current_user: UserInfo,
    ) -> JobTeamResponse:
        employee_id = user_id
        self._get_hiring_request_or_raise(hiring_request_id)
        member = self.repo.get_member(hiring_request_id, employee_id)
        if not member:
            raise JobTeamMemberNotFoundException(employee_id)

        if body.is_owner is not None:
            self._assert_owner_assignment_allowed(current_user)

        self.repo.update_member(
            hiring_request_id,
            employee_id,
            is_owner=body.is_owner,
        )
        if body.role is not None or body.is_owner is not None:
            hr = self._get_hiring_request_or_raise(hiring_request_id)
            final_role = body.role
            if body.is_owner is True or body.role == "job_owner":
                final_role = "job_owner"
            self._notify_job_assignment(employee_id, hiring_request_id, hr.title, final_role or "recruiter")
        logger.info(
            "Job team member updated: hiring_request_id=%s employee_id=%d is_owner=%s",
            hiring_request_id, employee_id, body.is_owner,
        )
        return self.list_members(hiring_request_id)

    def remove_member(self, hiring_request_id: uuid.UUID, user_id: int) -> JobTeamResponse:
        employee_id = user_id
        self._get_hiring_request_or_raise(hiring_request_id)
        if not self.repo.get_member(hiring_request_id, employee_id):
            raise JobTeamMemberNotFoundException(employee_id)

        self.repo.remove_member(hiring_request_id, employee_id)
        logger.info("Job team member removed: hiring_request_id=%s employee_id=%d", hiring_request_id, employee_id)
        return self.list_members(hiring_request_id)

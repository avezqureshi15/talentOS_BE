import uuid

from sqlalchemy.orm import Session

from app.modules.job_teams.job_team_model import JobTeamMember
from app.modules.users.user_model import User


class JobTeamRepository:
    """Team-membership queries. ``employee_id`` is an ``employees.id``
    end-to-end: the FE picker sources it from ``/employees/`` and the
    ``job_team_members.employee_id`` column already points at employees."""

    def __init__(self, db: Session):
        self.db = db

    def list_members(self, hiring_request_id: uuid.UUID) -> list[tuple[JobTeamMember, User]]:
        return (
            self.db.query(JobTeamMember, User)
            .join(User, User.employee_id == JobTeamMember.employee_id)
            .filter(JobTeamMember.hiring_request_id == hiring_request_id)
            .order_by(JobTeamMember.is_owner.desc(), User.name)
            .all()
        )

    def get_member(self, hiring_request_id: uuid.UUID, employee_id: int) -> JobTeamMember | None:
        return (
            self.db.query(JobTeamMember)
            .filter(
                JobTeamMember.hiring_request_id == hiring_request_id,
                JobTeamMember.employee_id == employee_id,
            )
            .first()
        )

    def add_member(
        self,
        hiring_request_id: uuid.UUID,
        employee_id: int,
        is_owner: bool = False,
    ) -> JobTeamMember:
        member = JobTeamMember(
            hiring_request_id=hiring_request_id,
            employee_id=employee_id,
            is_owner=is_owner,
        )
        self.db.add(member)
        self.db.commit()
        self.db.refresh(member)
        return member

    def update_member(
        self,
        hiring_request_id: uuid.UUID,
        employee_id: int,
        is_owner: bool | None = None,
    ) -> JobTeamMember | None:
        member = self.get_member(hiring_request_id, employee_id)
        if member is None:
            return None
        if is_owner is not None:
            member.is_owner = is_owner
        self.db.commit()
        self.db.refresh(member)
        return member

    def remove_member(self, hiring_request_id: uuid.UUID, employee_id: int) -> None:
        member = self.get_member(hiring_request_id, employee_id)
        if member:
            self.db.delete(member)
            self.db.commit()

    def count_members(self, hiring_request_id: uuid.UUID) -> int:
        return (
            self.db.query(JobTeamMember)
            .filter(JobTeamMember.hiring_request_id == hiring_request_id)
            .count()
        )

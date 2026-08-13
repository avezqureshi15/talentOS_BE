"""Job-level access control: tenant scoping + membership visibility.

Roles are global-only. A user's effective permissions come from their org
role (``User.permissions`` in the JWT). Job team membership is a plain
"who is on this job" list whose only access effect is visibility: non-admin
roles see only the jobs they are assigned to.

- ``resolve_job_access`` is the single source of truth for "can this user act
  on this job". ``require_job_access`` (FastAPI dependency) and
  ``scope_job_query`` (list filtering) build on it, so future modules
  (applications, reviews, slots, evaluations, AI) can reuse identical access
  semantics.
- ``min_role`` floors in ``require_job_access`` are checked against the
  caller's global role rank (superadmin > account_admin > job_owner >
  recruiter > reviewer).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.orm import Query, Session

from app.core.permissions import Permission, mark_enforced
from app.db.session import get_db
from app.modules.auth.auth_dependencies import get_current_user
from app.modules.auth.auth_schema import UserInfo
from app.modules.hiring_requests.hiring_request_model import HiringRequest
from app.modules.job_teams.job_team_model import JobTeamMember
from app.modules.users.user_model import User

GLOBAL_ROLE_RANK: dict[str, int] = {
    "superadmin": 4,
    "account_admin": 3,
    "job_owner": 2,
    "recruiter": 1,
    "reviewer": 0,
}


@dataclass
class JobAccessContext:
    """Result of an access check for a single job.

    ``member`` is None for org-level access (superadmin / account_admin on
    their tenant's jobs); otherwise it is the caller's JobTeamMember row,
    which only grants visibility — permissions always come from the user's
    global role.
    """

    user: UserInfo
    job: HiringRequest
    member: JobTeamMember | None = None

    @property
    def is_org_access(self) -> bool:
        return self.member is None

    @property
    def role_rank(self) -> int:
        return GLOBAL_ROLE_RANK.get(self.user.role, 0)

    def has_permission(self, permission: Permission) -> bool:
        return permission.value in self.user.permissions

    def ensure_permission(self, permission: Permission) -> None:
        mark_enforced(permission)
        if not self.has_permission(permission):
            raise HTTPException(status_code=403, detail=f"Missing required permission: {permission.value}")

    def ensure_min_role(self, min_role: str | None = None) -> None:
        if min_role is None:
            return
        if min_role not in GLOBAL_ROLE_RANK:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid role: {min_role}. Allowed: {', '.join(GLOBAL_ROLE_RANK)}",
            )
        if self.role_rank >= GLOBAL_ROLE_RANK[min_role]:
            return
        raise HTTPException(status_code=403, detail=f"Requires role at least {min_role}")


def resolve_job_access(db: Session, user: UserInfo, hiring_request_id: uuid.UUID) -> JobAccessContext:
    """Resolve access to a single job. 404 if the job does not exist, 403 if the
    caller has no access (tenant mismatch or no team membership)."""
    job = db.scalar(
        select(HiringRequest).where(
            HiringRequest.id == hiring_request_id,
            HiringRequest.deleted_at.is_(None),
        )
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Hiring request not found")

    if user.role == "superadmin":
        return JobAccessContext(user=user, job=job)

    if user.role == "account_admin":
        if job.tenant_id is not None and job.tenant_id == user.tenant_id:
            return JobAccessContext(user=user, job=job)
        raise HTTPException(status_code=403, detail="No access to this hiring request")

    # API keys cannot be job-team members, so a tenant-scoped key gets
    # org-level access within its tenant regardless of the role preset
    # (account_admin / job_owner / recruiter / reviewer) — the role still
    # controls which permission bits are granted.
    if user.is_api_key and user.tenant_id is not None:
        if job.tenant_id is not None and job.tenant_id == user.tenant_id:
            return JobAccessContext(user=user, job=job)
        raise HTTPException(status_code=403, detail="No access to this hiring request")

    member = db.scalar(
        select(JobTeamMember).where(
            JobTeamMember.hiring_request_id == job.id,
            _membership_predicate(db, user),
        )
    )
    if member is None:
        raise HTTPException(status_code=403, detail="No access to this hiring request")
    return JobAccessContext(user=user, job=job, member=member)


def _membership_predicate(db: Session, user: UserInfo):
    """Return the predicate that identifies ``user`` on ``job_team_members``
    via the employees linkage."""
    employee_id = db.scalar(select(User.employee_id).where(User.id == user.id))
    if employee_id is None:
        # No linked employee → no membership.
        return JobTeamMember.id == uuid.UUID(int=0)
    return JobTeamMember.employee_id == employee_id


def require_job_access(min_role: str | None = None, permission: Permission | None = None):
    """FastAPI dependency factory for job-scoped endpoints.

    Usage:
        @router.get("/{hiring_request_id}")
        def get_job(
            ctx: JobAccessContext = Depends(require_job_access()),
            ...
        ):

    The dependency reads the ``hiring_request_id`` path parameter (same name
    used across the hiring-requests and job-teams routers), resolves access,
    then enforces the optional role floor and/or explicit permission.
    """
    def checker(
        hiring_request_id: uuid.UUID = Path(..., alias="hiring_request_id"),
        current_user: UserInfo = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> JobAccessContext:
        context = resolve_job_access(db, current_user, hiring_request_id)
        context.ensure_min_role(min_role)
        if permission is not None:
            context.ensure_permission(permission)
        return context

    if permission is not None:
        mark_enforced(permission)
    return checker


def scope_job_query(query: Query, user: UserInfo) -> Query:
    """Restrict a HiringRequest query to the jobs the caller can access.

    superadmin -> unrestricted
    account_admin -> jobs of the caller's tenant
    everyone else -> jobs where the caller is a team member
    """
    if user.role == "superadmin":
        return query
    if user.role == "account_admin":
        return query.filter(HiringRequest.tenant_id == user.tenant_id)
    if user.is_api_key and user.tenant_id is not None:
        return query.filter(HiringRequest.tenant_id == user.tenant_id)
    predicate = _membership_predicate(query.session, user)
    member_jobs = (
        select(JobTeamMember.hiring_request_id)
        .join(HiringRequest, HiringRequest.id == JobTeamMember.hiring_request_id)
        .where(
            predicate,
            HiringRequest.deleted_at.is_(None),
        )
    )
    return query.filter(HiringRequest.id.in_(member_jobs))


def can_create_job(db: Session, user: UserInfo) -> bool:
    """Whether the caller may create hiring requests.

    superadmin/account_admin/job_owner always; otherwise anyone whose org role
    carries hiring_request.create.
    """
    if user.role in ("superadmin", "account_admin", "job_owner"):
        return True
    return Permission.HIRING_REQUEST_CREATE.value in user.permissions

"""Job-level access control: tenant scoping + job-team role hierarchy.

Extensible by design:
- ``JOB_ROLE_RANK`` / ``JOB_ROLE_PERMISSIONS`` are the single configuration
  points. Adding a new job-level role requires only extending these maps; no
  endpoint changes.
- ``resolve_job_access`` is the single source of truth for "can this user act
  on this job". ``require_job_access`` (FastAPI dependency) and
  ``scope_job_query`` (list filtering) build on it, so future modules
  (applications, reviews, slots, evaluations, AI) can reuse identical access
  semantics.

Hierarchy (config-driven, higher ranks inherit lower ones):
    org access (superadmin / account_admin) > job_owner > recruiter > reviewer

Effective permissions for a job = caller's JWT org permissions
UNION the permissions of their team role on that job.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.orm import Query, Session

from app.core.permissions import DEFAULT_ROLE_PERMISSIONS, Permission
from app.db.session import get_db
from app.modules.auth.auth_dependencies import get_current_user
from app.modules.auth.auth_schema import UserInfo
from app.modules.hiring_requests.hiring_request_model import HiringRequest
from app.modules.job_teams.job_team_model import JobTeamMember

JOB_ROLE_RANK: dict[str, int] = {
    "job_owner": 3,
    "recruiter": 2,
    "reviewer": 1,
}

JOB_ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    role: set(DEFAULT_ROLE_PERMISSIONS[role]) for role in JOB_ROLE_RANK
}

ORG_ACCESS_RANK = max(JOB_ROLE_RANK.values()) + 1


def validate_job_role(role: str) -> str:
    """Validate a job-level role string; raises 400 for unknown roles."""
    if role not in JOB_ROLE_RANK:
        raise HTTPException(status_code=400, detail=f"Invalid job role: {role}. Allowed: {', '.join(JOB_ROLE_RANK)}")
    return role


@dataclass
class JobAccessContext:
    """Result of an access check for a single job.

    ``member`` is None for org-level access (superadmin / account_admin on
    their tenant's jobs); otherwise it is the caller's JobTeamMember row,
    whose ``role`` drives the team-role permission set.
    """

    user: UserInfo
    job: HiringRequest
    member: JobTeamMember | None = None

    @property
    def is_org_access(self) -> bool:
        return self.member is None

    @property
    def team_role(self) -> str | None:
        return self.member.role if self.member else None

    @property
    def role_rank(self) -> int:
        if self.member is None:
            return ORG_ACCESS_RANK
        return JOB_ROLE_RANK.get(self.member.role, 0)

    def has_permission(self, permission: Permission) -> bool:
        if permission.value in self.user.permissions:
            return True
        if self.member is not None:
            return permission in JOB_ROLE_PERMISSIONS.get(self.member.role, set())
        return False

    def ensure_permission(self, permission: Permission) -> None:
        if not self.has_permission(permission):
            raise HTTPException(status_code=403, detail=f"Missing required permission: {permission.value}")

    def ensure_min_role(self, min_role: str | None = None) -> None:
        if min_role is None:
            return
        validate_job_role(min_role)
        if self.role_rank >= JOB_ROLE_RANK[min_role]:
            return
        raise HTTPException(status_code=403, detail=f"Requires job role at least {min_role} on this hiring request")


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

    member = db.scalar(
        select(JobTeamMember).where(
            JobTeamMember.hiring_request_id == job.id,
            JobTeamMember.user_id == user.id,
        )
    )
    if member is None:
        raise HTTPException(status_code=403, detail="No access to this hiring request")
    return JobAccessContext(user=user, job=job, member=member)


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
    member_jobs = (
        select(JobTeamMember.hiring_request_id)
        .join(HiringRequest, HiringRequest.id == JobTeamMember.hiring_request_id)
        .where(
            JobTeamMember.user_id == user.id,
            HiringRequest.deleted_at.is_(None),
        )
    )
    return query.filter(HiringRequest.id.in_(member_jobs))


def can_create_job(db: Session, user: UserInfo) -> bool:
    """Whether the caller may create hiring requests.

    superadmin/account_admin always; otherwise anyone whose org role carries
    hiring_request.create (org-level job_owner) or who is a job_owner on any
    team (team-role elevation).
    """
    if user.role in ("superadmin", "account_admin"):
        return True
    if Permission.HIRING_REQUEST_CREATE.value in user.permissions:
        return True
    return (
        db.scalar(
            select(JobTeamMember.id)
            .join(HiringRequest, HiringRequest.id == JobTeamMember.hiring_request_id)
            .where(
                JobTeamMember.user_id == user.id,
                JobTeamMember.role == "job_owner",
                HiringRequest.deleted_at.is_(None),
            )
            .limit(1)
        )
        is not None
    )


def resolve_effective_job_permissions(db: Session, user: UserInfo, hiring_request_id: uuid.UUID) -> set[str]:
    """Permissions a user effectively holds on a job (JWT perms ∪ team-role perms).

    Utility for consumers that need the permission set itself (e.g. FE meta)
    rather than endpoint gating.
    """
    context = resolve_job_access(db, user, hiring_request_id)
    effective = set(context.user.permissions)
    if context.member is not None:
        effective |= {p.value for p in JOB_ROLE_PERMISSIONS.get(context.member.role, set())}
    return effective

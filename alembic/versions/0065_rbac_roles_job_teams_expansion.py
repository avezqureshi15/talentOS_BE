"""rbac roles table, job team members, role expansion and admin rename

Revision ID: 0065
Revises: 0064
Create Date: 2026-08-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0065"
down_revision = "0064"
branch_labels = None
depends_on = None

NEW_PERMISSIONS = {
    "report.export": ("Report Export", "report", "GET /api/v1/hiring-requests/{id}/export"),
    "application.workflow": (
        "Application Workflow",
        "application",
        "PATCH /api/v1/applications/{candidate_id}/round-status, POST /api/v1/applications/candidates/{candidate_id}/move-to-next-round",
    ),
    "interview.plan_edit": (
        "Interview Plan Edit",
        "interview",
        "PUT /api/v1/hiring-requests/{id}/ai/questions",
    ),
    "job.team_manage": (
        "Job Team Manage",
        "job",
        "POST /api/v1/hiring-requests/{id}/team, PATCH /api/v1/hiring-requests/{id}/team/{user_id}, DELETE /api/v1/hiring-requests/{id}/team/{user_id}",
    ),
}

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "account_admin": [
        "application.view", "application.evaluate", "application.reject",
        "application.workflow", "report.export", "interview.plan_edit",
        "job.team_manage", "hiring_request.create", "hiring_request.edit",
        "hiring_request.view", "hiring_request.delete", "user.invite",
        "user.manage", "api_key.manage", "settings.view", "settings.edit",
        "slot.view_all", "review.submit", "review.view_all", "chat",
    ],
    "job_owner": [
        "application.view", "application.evaluate", "application.reject",
        "application.workflow", "report.export", "interview.plan_edit",
        "job.team_manage", "hiring_request.create", "hiring_request.edit",
        "hiring_request.view", "slot.view_all", "review.submit",
        "review.view_all", "chat",
    ],
    "recruiter": [
        "application.view", "application.evaluate", "application.reject",
        "application.workflow", "report.export", "hiring_request.edit",
        "hiring_request.view", "slot.view_all", "review.submit",
        "review.view_all", "chat",
    ],
    "reviewer": [
        "application.view", "application.evaluate", "application.reject",
        "report.export", "hiring_request.view", "chat",
    ],
}

LEGACY_ADDITIONS: dict[str, list[str]] = {
    "hr": ["report.export", "interview.plan_edit"],
    "viewer": ["report.export"],
}

SUPERADMIN_ADDITIONS: list[str] = [
    "report.export",
    "application.workflow",
    "interview.plan_edit",
    "job.team_manage",
]

ALL_ROLES = [
    ("superadmin", "Platform-wide administrator", True),
    ("account_admin", "Organization administrator", True),
    ("job_owner", "Owns and manages specific job listings", True),
    ("recruiter", "Manages candidates and application workflow", True),
    ("reviewer", "Reviews candidates and submits feedback", True),
    ("hr", "Legacy HR role", True),
    ("viewer", "Read-only access", True),
]


def _ensure_permissions(conn) -> None:
    for code, (name, group, endpoint) in NEW_PERMISSIONS.items():
        exists = conn.execute(
            sa.text("SELECT 1 FROM permissions WHERE code = :code").bindparams(code=code)
        ).scalar()
        if not exists:
            conn.execute(
                sa.text(
                    "INSERT INTO permissions (code, name, \"group\", endpoint, is_default) "
                    "VALUES (:code, :name, :group, :endpoint, true)"
                ).bindparams(code=code, name=name, group=group, endpoint=endpoint)
            )


def _sync_role_permissions(conn, role_name: str, permission_codes: list[str]) -> None:
    for code in permission_codes:
        conn.execute(
            sa.text(
                "INSERT INTO role_permissions (role_name, permission_code) "
                "SELECT :role, :code WHERE NOT EXISTS ("
                "  SELECT 1 FROM role_permissions "
                "  WHERE role_name = :role AND permission_code = :code)"
            ).bindparams(role=role_name, code=code)
        )


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("role_name", sa.String(length=100), nullable=False, unique=True),
        sa.Column("description", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_roles_role_name", "roles", ["role_name"])

    op.create_table(
        "job_team_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "hiring_request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hiring_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("is_owner", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("hiring_request_id", "user_id", name="uq_job_team_member"),
    )
    op.create_index("ix_job_team_members_hiring_request_id", "job_team_members", ["hiring_request_id"])
    op.create_index("ix_job_team_members_user_id", "job_team_members", ["user_id"])

    conn = op.get_bind()

    for role_name, description, is_system in ALL_ROLES:
        conn.execute(
            sa.text(
                "INSERT INTO roles (role_name, description, is_system) "
                "VALUES (:role, :description, :is_system) "
                "ON CONFLICT (role_name) DO NOTHING"
            ).bindparams(role=role_name, description=description, is_system=is_system)
        )

    _ensure_permissions(conn)

    conn.execute(sa.text("UPDATE users SET role = 'account_admin' WHERE role = 'admin'"))
    conn.execute(
        sa.text("UPDATE role_permissions SET role_name = 'account_admin' WHERE role_name = 'admin'")
    )
    conn.execute(
        sa.text("UPDATE tenant_invites SET role = 'account_admin' WHERE role = 'admin'")
    )

    for role_name, permission_codes in ROLE_PERMISSIONS.items():
        _sync_role_permissions(conn, role_name, permission_codes)

    for role_name, permission_codes in LEGACY_ADDITIONS.items():
        _sync_role_permissions(conn, role_name, permission_codes)

    _sync_role_permissions(conn, "superadmin", SUPERADMIN_ADDITIONS)

    conn.execute(
        sa.text(
            "UPDATE users SET role = 'viewer' "
            "WHERE role NOT IN ('superadmin', 'account_admin', 'job_owner', 'recruiter', 'reviewer', 'hr', 'viewer')"
        )
    )


def downgrade() -> None:
    op.drop_index("ix_job_team_members_user_id", table_name="job_team_members")
    op.drop_index("ix_job_team_members_hiring_request_id", table_name="job_team_members")
    op.drop_table("job_team_members")

    op.drop_index("ix_roles_role_name", table_name="roles")
    op.drop_table("roles")

    conn = op.get_bind()
    for code in NEW_PERMISSIONS:
        conn.execute(
            sa.text("DELETE FROM role_permissions WHERE permission_code = :code")
        ).bindparams(code=code)
    for code in NEW_PERMISSIONS:
        conn.execute(
            sa.text("DELETE FROM permissions WHERE code = :code")
        ).bindparams(code=code)

    conn.execute(sa.text("UPDATE users SET role = 'admin' WHERE role = 'account_admin'"))
    conn.execute(
        sa.text("UPDATE role_permissions SET role_name = 'admin' WHERE role_name = 'account_admin'")
    )
    conn.execute(
        sa.text("UPDATE tenant_invites SET role = 'admin' WHERE role = 'account_admin'")
    )

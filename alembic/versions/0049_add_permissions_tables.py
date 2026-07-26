"""add permissions and role_permissions tables with seed data

Revision ID: 0049
Revises: 0048
Create Date: 2026-07-25

"""
from __future__ import annotations

from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "0049"
down_revision: str | None = "0048"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


PERMISSION_DEFINITIONS: list[dict[str, str]] = [
    {"code": "application.view",         "name": "View Applications",         "group": "application"},
    {"code": "application.evaluate",     "name": "Evaluate Applications",     "group": "application"},
    {"code": "application.reject",       "name": "Reject Applications",       "group": "application"},
    {"code": "hiring_request.create",    "name": "Create Hiring Requests",    "group": "hiring_request"},
    {"code": "hiring_request.edit",      "name": "Edit Hiring Requests",      "group": "hiring_request"},
    {"code": "hiring_request.view",      "name": "View Hiring Requests",      "group": "hiring_request"},
    {"code": "hiring_request.delete",    "name": "Delete Hiring Requests",    "group": "hiring_request"},
    {"code": "user.invite",              "name": "Invite Users",              "group": "user"},
    {"code": "user.manage",              "name": "Manage Users",              "group": "user"},
    {"code": "tenant.view",              "name": "View Tenant Settings",      "group": "tenant"},
    {"code": "tenant.edit",              "name": "Edit Tenant Settings",      "group": "tenant"},
    {"code": "settings.view",            "name": "View Settings",             "group": "settings"},
    {"code": "settings.edit",            "name": "Edit Settings",             "group": "settings"},
    {"code": "slot.submit",              "name": "Submit Slots",              "group": "slot"},
    {"code": "slot.view_all",            "name": "View All Slots",            "group": "slot"},
    {"code": "review.submit",            "name": "Submit Reviews",            "group": "review"},
    {"code": "review.view_all",          "name": "View All Reviews",          "group": "review"},
    {"code": "chat",                     "name": "Use Chat",                  "group": "chat"},
]

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "superadmin": [p["code"] for p in PERMISSION_DEFINITIONS],
    "admin": [
        "application.view",
        "application.evaluate",
        "application.reject",
        "hiring_request.create",
        "hiring_request.edit",
        "hiring_request.view",
        "hiring_request.delete",
        "user.invite",
        "user.manage",
        "settings.view",
        "settings.edit",
        "slot.view_all",
        "review.submit",
        "review.view_all",
        "chat",
    ],
    "hr": [
        "application.view",
        "application.evaluate",
        "application.reject",
        "hiring_request.create",
        "hiring_request.edit",
        "hiring_request.view",
        "slot.view_all",
        "review.submit",
        "review.view_all",
        "chat",
    ],
    "viewer": [
        "application.view",
        "hiring_request.view",
        "chat",
    ],
}


def upgrade() -> None:
    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("group", sa.String(50), nullable=False, server_default="general"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_permission_code"),
    )
    op.create_index("ix_permissions_code", "permissions", ["code"])

    op.create_table(
        "role_permissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("role_name", sa.String(100), nullable=False),
        sa.Column("permission_code", sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role_name", "permission_code", name="uq_role_permission"),
    )
    op.create_index("ix_role_permissions_role_name", "role_permissions", ["role_name"])

    permissions_table = sa.table(
        "permissions",
        sa.Column("code", sa.String),
        sa.Column("name", sa.String),
        sa.Column("group", sa.String),
    )
    op.bulk_insert(permissions_table, PERMISSION_DEFINITIONS)

    role_perms_table = sa.table(
        "role_permissions",
        sa.Column("role_name", sa.String),
        sa.Column("permission_code", sa.String),
    )
    rows = []
    for role_name, codes in ROLE_PERMISSIONS.items():
        for code in codes:
            rows.append({"role_name": role_name, "permission_code": code})
    op.bulk_insert(role_perms_table, rows)


def downgrade() -> None:
    op.drop_table("role_permissions")
    op.drop_table("permissions")

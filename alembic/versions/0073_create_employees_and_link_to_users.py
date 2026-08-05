"""create employees table and link users.employee_id

Phase 1 of the users↔employees split. Reads stay on users; this migration
only creates the new table, backfills it 1:1 from users, and adds an
optional users.employee_id back-pointer so future joins are cheap.

Revision ID: 0073
Revises: 0072
Create Date: 2026-08-04

"""
from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "0073"
down_revision: str | None = "0072"
branch_labels: ClassVar[list[str] | None] = None
depends_on: ClassVar[list[str] | None] = None


def upgrade() -> None:
    op.create_table(
        "employees",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("emp_id", sa.String(50), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("personal_email", sa.String(255), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("contact_number", sa.String(20), nullable=True),
        sa.Column("hrms_id", sa.String(100), nullable=True),
        sa.Column("designation", sa.String(255), nullable=True),
        sa.Column("department", sa.String(255), nullable=True),
        sa.Column("work_mode", sa.String(50), nullable=True),
        sa.Column("delivery_status", sa.String(50), nullable=True),
        sa.Column("work_location_type", sa.String(50), nullable=True),
        sa.Column("doj", sa.Date(), nullable=True),
        sa.Column("doe", sa.Date(), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("internship_duration", sa.Integer(), nullable=True),
        sa.Column("band", sa.String(50), nullable=True),
        sa.Column("skills", sa.Text(), nullable=True),
        sa.Column("status", sa.String(50), nullable=True),
        sa.Column("user_type", sa.String(50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_employees_email", "employees", ["email"], unique=True)
    op.create_index("ix_employees_emp_id", "employees", ["emp_id"], unique=True)
    op.create_index("ix_employees_tenant_id", "employees", ["tenant_id"])
    op.create_index("ix_employees_hrms_id", "employees", ["hrms_id"])

    op.execute(
        """
        INSERT INTO employees (
            tenant_id, emp_id, email, personal_email, name, contact_number,
            hrms_id, designation, department, work_mode, delivery_status,
            work_location_type, doj, doe, date_of_birth, internship_duration,
            band, skills, status, user_type, created_at
        )
        SELECT DISTINCT ON (u.email)
            u.tenant_id, u.emp_id, u.email, u.personal_email, u.name, u.phone_number,
            NULL, u.designation, u.department, u.work_mode, u.delivery_status,
            u.work_location_type, u.doj, u.doe, u.date_of_birth, u.internship_duration,
            u.band, u.skills, u.status, u.user_type, u.created_at
        FROM users u
        WHERE u.email IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM employees e WHERE e.email = u.email)
        ORDER BY u.email, u.id
        """
    )

    op.add_column(
        "users",
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=True),
    )
    op.create_index(
        "ix_users_employee_id",
        "users",
        ["employee_id"],
        unique=True,
        postgresql_where=sa.text("employee_id IS NOT NULL"),
    )

    op.execute(
        """
        UPDATE users u
        SET employee_id = e.id
        FROM employees e
        WHERE u.email = e.email
          AND u.employee_id IS NULL
          AND u.id = (
              SELECT MIN(u2.id) FROM users u2 WHERE u2.email = e.email
          )
        """
    )


def downgrade() -> None:
    op.drop_index("ix_users_employee_id", table_name="users")
    op.drop_column("users", "employee_id")

    op.drop_index("ix_employees_hrms_id", table_name="employees")
    op.drop_index("ix_employees_tenant_id", table_name="employees")
    op.drop_index("ix_employees_emp_id", table_name="employees")
    op.drop_index("ix_employees_email", table_name="employees")
    op.drop_table("employees")

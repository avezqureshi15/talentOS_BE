"""Backfill users rows for employees that were imported into the directory but
never got a linked auth account (the users<->employees dual-write transition).

Creates a login-less User row (password_hash=None, role="") for every
``employees`` row that has no linked user, copying emp_id/email/name and
setting ``users.employee_id`` so form/mail flows (e.g. POST /ask-form) resolve.

Usage:
    python scripts/backfill_users_for_employees.py [--dry-run]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import Session  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.modules.employees.employee_model import Employee  # noqa: E402
from app.modules.tenants.tenant_model import Tenant  # noqa: E402
from app.modules.users.user_model import User  # noqa: E402


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    db: Session = SessionLocal()
    try:
        employees = db.query(Employee).all()
        print(f"Found {len(employees)} employee(s) in directory")

        created = 0
        skipped = 0
        for employee in employees:
            linked = (
                db.query(User)
                .filter(
                    (User.employee_id == employee.id) | (User.email == employee.email)
                )
                .first()
            )
            if linked:
                print(
                    f"  SKIP {employee.emp_id}: already linked to user id={linked.id} "
                    f"(emp_id={linked.emp_id!r})"
                )
                skipped += 1
                continue

            collision = db.query(User).filter(
                (User.emp_id == employee.emp_id) | (User.email == employee.email)
            ).first()
            if collision:
                print(
                    f"  SKIP {employee.emp_id}: emp_id/email collision with user id={collision.id}"
                )
                skipped += 1
                continue

            print(
                f"  CREATE {employee.emp_id}: {employee.name} <{employee.email}> "
                f"(tenant_id={employee.tenant_id})"
            )
            if not dry_run:
                user = User(
                    emp_id=employee.emp_id,
                    email=employee.email,
                    name=employee.name,
                    password_hash=None,
                    auth_provider="email",
                    tenant_id=employee.tenant_id,
                    employee_id=employee.id,
                    role="",
                    is_active=True,
                    status="active",
                )
                db.add(user)
                created += 1

        if not dry_run:
            db.commit()
            print(f"Committed {created} user(s); skipped {skipped}")
        else:
            print(f"Dry run - would create {created} (no changes written); skipped {skipped}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

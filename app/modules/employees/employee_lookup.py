"""Small helpers for the users↔employees dual-write transition."""

from sqlalchemy.orm import Session

from app.modules.employees.employee_model import Employee
from app.modules.users.user_model import User


def user_id_to_employee_id(db: Session, user_id: int) -> int | None:
    """Resolve a user id to its linked employee id via ``users.employee_id``.

    Returns ``None`` for users without a matching employee row (e.g. an
    invited user that was created after the 0073 backfill and hasn't been
    linked yet). Dual-write callers store the ``None`` verbatim; Phase 3
    tightens this up.
    """
    return db.query(User.employee_id).filter(User.id == user_id).scalar()


def ensure_employee_for_user(db: Session, user: User) -> Employee:
    """Guarantee a linked employee row exists for ``user``.

    Reuses an existing ``employees`` row when one already matches by
    email (backfill 0073 or previous invite), otherwise creates a fresh
    one copying HR-shaped fields off the user. Sets ``user.employee_id``
    on the caller's session; the caller is responsible for the commit.

    Idempotent — safe to call from any user-creation path.
    """
    if user.employee_id is not None:
        return db.query(Employee).filter(Employee.id == user.employee_id).first()

    existing = db.query(Employee).filter(Employee.email == user.email).first()
    if existing:
        user.employee_id = existing.id
        return existing

    # HR fields no longer live on the user row; seed with minimal defaults
    # so pickers and joins have something to render. HR admin fills the rest
    # via /employees CRUD.
    employee = Employee(
        tenant_id=user.tenant_id,
        emp_id=user.emp_id,
        email=user.email,
        name=user.name,
        status=user.status,
        designation="Unassigned",
        department="Unassigned",
    )
    db.add(employee)
    db.flush()
    user.employee_id = employee.id
    return employee

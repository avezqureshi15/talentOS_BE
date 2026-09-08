from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.modules.auth.invite_model import TenantInvite
from app.modules.employees.employee_directory_repository import EmployeeDirectoryRepository
from app.modules.employees.employee_model import Employee
from app.modules.employees.employee_router import list_employees
from app.modules.tenants.tenant_model import Tenant
from app.modules.users.user_model import User


def _sqlite_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Tenant.__table__.create(engine)
    Employee.__table__.create(engine)
    User.__table__.create(engine)
    TenantInvite.__table__.create(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def _employee(db, *, emp_id: str, email: str, name: str, tenant_id: int = 1) -> Employee:
    emp = Employee(tenant_id=tenant_id, emp_id=emp_id, email=email, name=name)
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


def _user(db, *, emp_id: str, email: str, name: str, employee_id: int | None = None) -> User:
    user = User(
        emp_id=emp_id,
        email=email,
        name=name,
        tenant_id=1,
        employee_id=employee_id,
        status="active",
        role="reviewer",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _pending_invite(db, *, email: str, tenant_id: int = 1, invited_by_user_id: int = 1) -> TenantInvite:
    invite = TenantInvite(
        tenant_id=tenant_id,
        email=email,
        role="reviewer",
        token=f"tok-{email}",
        invited_by_user_id=invited_by_user_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return invite


def test_invite_eligible_excludes_linked_user() -> None:
    db = _sqlite_session()
    eligible = _employee(db, emp_id="EMP001", email="open@example.com", name="Open")
    linked = _employee(db, emp_id="EMP002", email="linked@example.com", name="Linked")
    _user(db, emp_id="U002", email="linked@example.com", name="Linked", employee_id=linked.id)

    rows, total = EmployeeDirectoryRepository(db).search_paginated(
        tenant_id=1, invite_eligible=True,
    )
    emails = {e.email for e in rows}
    assert eligible.email in emails
    assert linked.email not in emails
    assert total == 1


def test_invite_eligible_excludes_email_colliding_user() -> None:
    db = _sqlite_session()
    colliding = _employee(db, emp_id="EMP003", email="collide@example.com", name="Orphan")
    _user(db, emp_id="U003", email="collide@example.com", name="Existing User", employee_id=None)
    open_emp = _employee(db, emp_id="EMP004", email="free@example.com", name="Free")

    rows, _ = EmployeeDirectoryRepository(db).search_paginated(
        tenant_id=1, invite_eligible=True,
    )
    emails = {e.email for e in rows}
    assert colliding.email not in emails
    assert open_emp.email in emails


def test_invite_eligible_excludes_pending_invite() -> None:
    db = _sqlite_session()
    pending = _employee(db, emp_id="EMP005", email="pending@example.com", name="Pending")
    open_emp = _employee(db, emp_id="EMP006", email="clear@example.com", name="Free")
    _pending_invite(db, email=pending.email)

    rows, _ = EmployeeDirectoryRepository(db).search_paginated(
        tenant_id=1, invite_eligible=True,
    )
    emails = {e.email for e in rows}
    assert pending.email not in emails
    assert open_emp.email in emails


def test_default_list_includes_linked_employees() -> None:
    db = _sqlite_session()
    linked = _employee(db, emp_id="EMP007", email="admin@example.com", name="Admin")
    _user(db, emp_id="U007", email="admin@example.com", name="Admin", employee_id=linked.id)
    open_emp = _employee(db, emp_id="EMP008", email="open2@example.com", name="Open")

    rows, total = EmployeeDirectoryRepository(db).search_paginated(tenant_id=1)
    emails = {e.email for e in rows}
    assert linked.email in emails
    assert open_emp.email in emails
    assert total == 2


def test_list_employees_rejects_authorized_only_and_invite_eligible() -> None:
    with pytest.raises(HTTPException) as exc:
        list_employees(
            q=None,
            page=1,
            per_page=20,
            slotsInfo=False,
            authorized_only=True,
            invite_eligible=True,
            db=MagicMock(),
            current_user=SimpleNamespace(role="account_admin", tenant_id=1),
        )
    assert exc.value.status_code == 400
    assert "cannot be used together" in exc.value.detail

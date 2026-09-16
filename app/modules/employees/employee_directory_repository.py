from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, case, exists, func, or_
from sqlalchemy.orm import Query, Session

from app.modules.employees.employee_model import Employee


class EmployeeDirectoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_benched_by_designation(
        self, designation: str, tenant_id: int | None = None
    ) -> list[Employee]:
        query = self.db.query(Employee).filter(
            Employee.status == "benched",
            Employee.designation == designation,
        )
        if tenant_id is not None:
            query = query.filter(Employee.tenant_id == tenant_id)
        return query.order_by(Employee.name).all()

    def get_by_emp_id(self, emp_id: str) -> Employee | None:
        return self.db.query(Employee).filter(Employee.emp_id == emp_id).first()

    def get_by_email(self, email: str) -> Employee | None:
        return self.db.query(Employee).filter(Employee.email == email).first()

    def _apply_invite_eligible_filter(self, base_query: Query, tenant_id: int | None) -> Query:
        from app.modules.auth.invite_model import TenantInvite
        from app.modules.users.user_model import User

        linked_user = exists().where(User.employee_id == Employee.id)
        email_user = exists().where(User.email == Employee.email)

        invite_clauses = [
            TenantInvite.email == Employee.email,
            TenantInvite.accepted_at.is_(None),
            TenantInvite.expires_at > datetime.now(timezone.utc),
        ]
        if tenant_id is not None:
            invite_clauses.append(TenantInvite.tenant_id == tenant_id)
        pending_invite = exists().where(and_(*invite_clauses))

        return base_query.filter(~linked_user, ~email_user, ~pending_invite)

    def search_paginated(
        self,
        query: str | None = None,
        page: int = 1,
        per_page: int = 20,
        slots_info: bool = False,
        tenant_id: int | None = None,
        authorized_only: bool = False,
        invite_eligible: bool = False,
        has_slots: bool | None = None,
        slot_form_status: str | None = None,
        department: str | None = None,
    ) -> tuple[list[Employee] | list[tuple], int]:
        base_query = self.db.query(Employee)

        if tenant_id is not None:
            base_query = base_query.filter(Employee.tenant_id == tenant_id)

        if department:
            base_query = base_query.filter(Employee.department == department)

        if authorized_only:
            from app.modules.users.user_model import User
            base_query = (
                base_query
                .join(User, User.employee_id == Employee.id)
                .filter(
                    User.is_active == True,
                    User.role.isnot(None),
                    User.role != "",
                )
            )

        if invite_eligible:
            base_query = self._apply_invite_eligible_filter(base_query, tenant_id)

        if query:
            base_query = base_query.filter(
                or_(
                    Employee.name.ilike(f"%{query}%"),
                    Employee.email.ilike(f"%{query}%"),
                    Employee.emp_id.ilike(f"%{query}%"),
                    Employee.designation.ilike(f"%{query}%"),
                    Employee.department.ilike(f"%{query}%"),
                )
            )

        total = base_query.count()

        if slots_info:
            from app.modules.forms.form_model import Form, FormStatus, FormType
            from app.modules.slots.slot_model import Slot, SlotStatus

            pending_form = exists().where(
                Form.employee_id == Employee.id,
                Form.type == FormType.SLOTS.value,
                Form.status == FormStatus.SENT.value,
            )
            submitted_form = exists().where(
                Form.employee_id == Employee.id,
                Form.type == FormType.SLOTS.value,
                Form.status == FormStatus.SUBMITTED.value,
            )
            slot_form_status_expr = case(
                (pending_form, "pending"),
                (submitted_form, "submitted"),
                else_="none",
            )

            activity_subq = (
                self.db.query(
                    Slot.employee_id.label("employee_id"),
                    func.max(Slot.updated_at).label("last_slot_activity"),
                )
                .group_by(Slot.employee_id)
                .subquery()
            )

            slots_query = (
                base_query.outerjoin(
                    Slot,
                    and_(
                        Slot.employee_id == Employee.id,
                        Slot.status == SlotStatus.AVAILABLE.value,
                        Slot.start_at > func.now(),
                    ),
                )
                .outerjoin(activity_subq, activity_subq.c.employee_id == Employee.id)
                .add_columns(
                    func.count(Slot.id).label("slots_count"),
                    activity_subq.c.last_slot_activity.label("last_slot_activity"),
                    slot_form_status_expr.label("slot_form_status"),
                )
                .group_by(Employee.id, activity_subq.c.last_slot_activity)
            )

            if has_slots is True:
                slots_query = slots_query.having(func.count(Slot.id) > 0)
            elif has_slots is False:
                slots_query = slots_query.having(func.count(Slot.id) == 0)

            if slot_form_status == "pending":
                slots_query = slots_query.filter(pending_form)
            elif slot_form_status == "submitted":
                slots_query = slots_query.filter(~pending_form, submitted_form)
            elif slot_form_status == "none":
                slots_query = slots_query.filter(~pending_form, ~submitted_form)

            if has_slots is not None or slot_form_status is not None:
                count_subq = slots_query.with_entities(Employee.id).subquery()
                total = self.db.query(func.count()).select_from(count_subq).scalar() or 0

            results = (
                slots_query.order_by(func.count(Slot.id).desc(), Employee.name.asc())
                .offset((page - 1) * per_page)
                .limit(per_page)
                .all()
            )
            return results, total

        employees = (
            base_query.order_by(Employee.name)
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return employees, total

    def get_distinct_departments(self, tenant_id: int | None = None) -> list[str]:
        query = self.db.query(Employee.department).filter(
            Employee.department.isnot(None),
            Employee.department != "",
        )
        if tenant_id is not None:
            query = query.filter(Employee.tenant_id == tenant_id)
        rows = query.distinct().order_by(Employee.department.asc()).all()
        return [row[0] for row in rows]

    def create(self, tenant_id: int | None, **fields: Any) -> Employee:
        employee = Employee(tenant_id=tenant_id, **fields)
        self.db.add(employee)
        self.db.commit()
        self.db.refresh(employee)
        return employee

    def update(self, employee: Employee, **fields: Any) -> Employee:
        for key, value in fields.items():
            setattr(employee, key, value)
        self.db.commit()
        self.db.refresh(employee)
        return employee

    def soft_delete(self, employee: Employee) -> Employee:
        employee.status = "inactive"
        self.db.commit()
        self.db.refresh(employee)
        return employee

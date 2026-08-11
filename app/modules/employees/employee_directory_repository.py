from typing import Any

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

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

    def search_paginated(
        self,
        query: str | None = None,
        page: int = 1,
        per_page: int = 20,
        slots_info: bool = False,
        tenant_id: int | None = None,
        authorized_only: bool = False,
    ) -> tuple[list[Employee] | list[tuple[Employee, int]], int]:
        base_query = self.db.query(Employee)

        if tenant_id is not None:
            base_query = base_query.filter(Employee.tenant_id == tenant_id)

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
            from app.modules.slots.slot_model import Slot, SlotStatus

            results = (
                base_query.outerjoin(
                    Slot,
                    and_(
                        Slot.employee_id == Employee.id,
                        Slot.status == SlotStatus.AVAILABLE.value,
                        Slot.start_at > func.now(),
                    ),
                )
                .add_columns(func.count(Slot.id).label("slots_count"))
                .group_by(Employee.id)
                .order_by(func.count(Slot.id).desc(), Employee.name.asc())
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

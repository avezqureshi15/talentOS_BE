from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.modules.users.user_model import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def search_paginated(
        self,
        query: str | None = None,
        page: int = 1,
        per_page: int = 20,
        slots_info: bool = False,
        tenant_id: int | None = None,
    ) -> tuple[list[User] | list[tuple[User, int]], int]:
        from app.modules.employees.employee_model import Employee
        # Join Employee (left) so we can search across HR fields; users
        # without a linked employee still show up.
        base_query = self.db.query(User).outerjoin(Employee, Employee.id == User.employee_id)

        if tenant_id is not None:
            base_query = base_query.filter(User.tenant_id == tenant_id)

        if query:
            filter_condition = or_(
                User.name.ilike(f"%{query}%"),
                User.email.ilike(f"%{query}%"),
                User.emp_id.ilike(f"%{query}%"),
                Employee.designation.ilike(f"%{query}%"),
                Employee.department.ilike(f"%{query}%"),
            )
            base_query = base_query.filter(filter_condition)

        total = base_query.count()

        if slots_info:
            from app.modules.slots.slot_model import Slot, SlotStatus
            results = (
                base_query.outerjoin(Slot, and_(
                    Slot.employee_id == User.employee_id,
                    Slot.status == SlotStatus.AVAILABLE.value,
                    Slot.start_at > func.now(),
                ))
                .add_columns(func.count(Slot.id).label("slots_count"))
                .group_by(User.id)
                .order_by(func.count(Slot.id).desc(), User.name.asc())
                .offset((page - 1) * per_page)
                .limit(per_page)
                .all()
            )
            return results, total

        users = (
            base_query.order_by(User.name)
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return users, total

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_emp_id(self, emp_id: str) -> User | None:
        return self.db.query(User).filter(User.emp_id == emp_id).first()

    def list_all(self, page: int = 1, per_page: int = 20, q: str | None = None, tenant_id: int | None = None) -> tuple[list[User], int]:
        query = self.db.query(User)
        if tenant_id is not None:
            query = query.filter(User.tenant_id == tenant_id)
        if q:
            query = query.filter(
                User.name.ilike(f"%{q}%") | User.email.ilike(f"%{q}%") | User.emp_id.ilike(f"%{q}%")
            )
        total = query.count()
        users = query.order_by(User.name).offset((page - 1) * per_page).limit(per_page).all()
        return users, total

    def create(self, **kwargs) -> User:
        user = User(**kwargs)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

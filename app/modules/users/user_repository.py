from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.modules.users.user_model import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_benched_by_designation(self, designation: str) -> list[User]:
        return (
            self.db.query(User)
            .filter(User.status == "benched", User.designation == designation)
            .order_by(User.name)
            .all()
        )

    def search_paginated(
        self,
        query: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[User], int]:
        stmt = self.db.query(User)

        if query:
            filter_condition = or_(
                User.name.ilike(f"%{query}%"),
                User.email.ilike(f"%{query}%"),
                User.emp_id.ilike(f"%{query}%"),
                User.designation.ilike(f"%{query}%"),
                User.department.ilike(f"%{query}%"),
            )
            stmt = stmt.filter(filter_condition)

        total = stmt.count()
        users = stmt.order_by(User.name).offset((page - 1) * per_page).limit(per_page).all()
        return users, total

    def get_by_emp_id(self, emp_id: str) -> User | None:
        return self.db.query(User).filter(User.emp_id == emp_id).first()

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def create(self, **kwargs) -> User:
        user = User(**kwargs)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

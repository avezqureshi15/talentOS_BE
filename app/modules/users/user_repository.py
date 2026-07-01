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

    def get_by_emp_id(self, emp_id: str) -> User | None:
        return self.db.query(User).filter(User.emp_id == emp_id).first()

    def list_all(self, page: int = 1, per_page: int = 20, q: str | None = None) -> tuple[list[User], int]:
        query = self.db.query(User)
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

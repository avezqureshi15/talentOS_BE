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

    def create(self, **kwargs) -> User:
        user = User(**kwargs)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

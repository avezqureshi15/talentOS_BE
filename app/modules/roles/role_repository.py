from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.modules.roles.role_model import RoleModel
from app.modules.users.permission_model import RolePermission
from app.modules.users.user_model import User


class RoleRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_name(self, role_name: str) -> RoleModel | None:
        return self.db.query(RoleModel).filter(RoleModel.role_name == role_name).first()

    def list_all(self) -> list[RoleModel]:
        return self.db.query(RoleModel).order_by(RoleModel.role_name).all()

    def list_role_names(self) -> list[str]:
        return [role.role_name for role in self.list_all()]

    def create(self, role_name: str, description: str, is_system: bool = False) -> RoleModel:
        role = RoleModel(role_name=role_name, description=description, is_system=is_system)
        self.db.add(role)
        self.db.commit()
        self.db.refresh(role)
        return role

    def delete(self, role_name: str) -> None:
        self.db.execute(delete(RolePermission).where(RolePermission.role_name == role_name))
        role = self.db.query(RoleModel).filter(RoleModel.role_name == role_name).first()
        if role:
            self.db.delete(role)
        self.db.commit()

    def get_permission_codes(self, role_name: str) -> list[str]:
        return self.db.execute(
            select(RolePermission.permission_code).where(RolePermission.role_name == role_name)
        ).scalars().all()

    def set_permission_codes(self, role_name: str, permission_codes: list[str]) -> None:
        self.db.execute(delete(RolePermission).where(RolePermission.role_name == role_name))
        for code in permission_codes:
            self.db.add(RolePermission(role_name=role_name, permission_code=code))
        self.db.commit()

    def role_permission_counts(self) -> dict[str, int]:
        rows = self.db.execute(
            select(RolePermission.role_name, func.count(RolePermission.permission_code).label("cnt"))
            .group_by(RolePermission.role_name)
        ).all()
        return {row.role_name: row.cnt for row in rows}

    def user_role_counts(self) -> dict[str, int]:
        rows = self.db.execute(
            select(User.role, func.count(User.id).label("cnt")).group_by(User.role)
        ).all()
        return {row.role: row.cnt for row in rows}

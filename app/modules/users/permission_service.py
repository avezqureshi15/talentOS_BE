from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import DEFAULT_ROLE_PERMISSIONS, Permission
from app.modules.users.permission_model import RolePermission


class PermissionService:
    def __init__(self, db: Session):
        self.db = db

    def get_permissions_for_role(self, role_name: str) -> list[str]:
        rows = self.db.execute(
            select(RolePermission.permission_code).where(
                RolePermission.role_name == role_name
            )
        ).scalars().all()
        if rows:
            return sorted(rows)
        default = DEFAULT_ROLE_PERMISSIONS.get(role_name)
        if default:
            return sorted(p.value for p in default)
        return []

    def user_has_permission(self, role_name: str, permission: Permission) -> bool:
        return permission.value in self.get_permissions_for_role(role_name)

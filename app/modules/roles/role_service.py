from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.permissions import DEFAULT_ROLE_PERMISSIONS, PERMISSION_META
from app.modules.roles.role_schema import PermissionInfo, RoleListItem, RoleResponse
from app.modules.users.permission_model import PermissionModel, RolePermission
from app.modules.users.user_model import User


class RoleService:
    def __init__(self, db: Session):
        self.db = db

    def list_roles(self) -> list[RoleListItem]:
        all_permission_rows = self.db.execute(
            select(RolePermission.role_name, func.count(RolePermission.permission_code).label("cnt"))
            .group_by(RolePermission.role_name)
        ).all()
        db_counts = {row.role_name: row.cnt for row in all_permission_rows}

        user_counts_raw = self.db.execute(
            select(User.role, func.count(User.id).label("cnt"))
            .group_by(User.role)
        ).all()
        user_counts = {row.role: row.cnt for row in user_counts_raw}

        all_role_names = set(db_counts.keys()) | set(DEFAULT_ROLE_PERMISSIONS.keys())
        items = []
        for role_name in sorted(all_role_names):
            perm_count = db_counts.get(role_name, len(DEFAULT_ROLE_PERMISSIONS.get(role_name, [])))
            items.append(RoleListItem(
                role_name=role_name,
                permission_count=perm_count,
                user_count=user_counts.get(role_name, 0),
            ))
        return items

    def get_role(self, role_name: str) -> RoleResponse | None:
        db_perms = self.db.execute(
            select(RolePermission.permission_code).where(
                RolePermission.role_name == role_name
            )
        ).scalars().all()
        assigned_set = set(db_perms) if db_perms else (
            {p.value for p in DEFAULT_ROLE_PERMISSIONS.get(role_name, set())}
        )

        all_permissions = self.db.execute(
            select(PermissionModel).order_by(PermissionModel.group, PermissionModel.code)
        ).scalars().all()

        if not all_permissions:
            all_permissions = [
                PermissionModel(code=code, name=meta["name"], group=meta["group"])
                for code, meta in PERMISSION_META.items()
            ]

        permissions = [
            PermissionInfo(
                code=p.code,
                name=p.name,
                group=p.group,
                assigned=p.code in assigned_set,
                endpoint=getattr(p, "endpoint", "") or "",
            )
            for p in all_permissions
        ]

        return RoleResponse(role_name=role_name, permissions=permissions)

    def list_all_permissions(self) -> list[PermissionInfo]:
        rows = self.db.execute(
            select(PermissionModel).order_by(PermissionModel.group, PermissionModel.code)
        ).scalars().all()

        if not rows:
            return [
                PermissionInfo(code=code, name=meta["name"], group=meta["group"])
                for code, meta in PERMISSION_META.items()
            ]

        return [
            PermissionInfo(code=r.code, name=r.name, group=r.group, endpoint=getattr(r, "endpoint", "") or "")
            for r in rows
        ]

    def update_role_permissions(self, role_name: str, permission_codes: list[str]) -> RoleResponse:
        self.db.execute(
            delete(RolePermission).where(RolePermission.role_name == role_name)
        )

        for code in permission_codes:
            self.db.add(RolePermission(role_name=role_name, permission_code=code))

        self.db.commit()

        return self.get_role(role_name)

from app.core.permissions import DEFAULT_ROLE_PERMISSIONS, PERMISSION_META
from app.modules.roles.role_repository import RoleRepository
from app.modules.roles.role_schema import PermissionInfo, RoleListItem, RoleResponse
from app.modules.users.permission_model import PermissionModel


class RoleService:
    def __init__(self, db):
        self.db = db
        self.repo = RoleRepository(db)

    def list_roles(self) -> list[RoleListItem]:
        db_counts = self.repo.role_permission_counts()
        user_counts = self.repo.user_role_counts()

        all_role_names = set(self.repo.list_role_names()) | set(DEFAULT_ROLE_PERMISSIONS.keys())
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
        db_perms = self.repo.get_permission_codes(role_name)
        assigned_set = set(db_perms) if db_perms else (
            {p.value for p in DEFAULT_ROLE_PERMISSIONS.get(role_name, set())}
        )

        all_permissions = self.db.query(PermissionModel).order_by(
            PermissionModel.group, PermissionModel.code
        ).all()

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
        rows = self.db.query(PermissionModel).order_by(
            PermissionModel.group, PermissionModel.code
        ).all()

        if not rows:
            return [
                PermissionInfo(code=code, name=meta["name"], group=meta["group"])
                for code, meta in PERMISSION_META.items()
            ]

        return [
            PermissionInfo(code=r.code, name=r.name, group=r.group, endpoint=getattr(r, "endpoint", "") or "")
            for r in rows
        ]

    def role_exists(self, role_name: str) -> bool:
        return self.repo.get_by_name(role_name) is not None

    def validate_role_name(self, role_name: str) -> None:
        known = set(DEFAULT_ROLE_PERMISSIONS.keys()) | set(self.repo.list_role_names())
        if role_name not in known:
            raise ValueError(f"Unknown role: {role_name}")

    def create_role(self, role_name: str, description: str = "") -> RoleResponse:
        self.repo.create(role_name=role_name, description=description)
        return self.get_role(role_name)

    def delete_role(self, role_name: str) -> None:
        self.repo.delete(role_name)

    def update_role_permissions(self, role_name: str, permission_codes: list[str]) -> RoleResponse:
        self.repo.set_permission_codes(role_name, permission_codes)
        return self.get_role(role_name)

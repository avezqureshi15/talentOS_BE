from pydantic import BaseModel, ConfigDict


class PermissionInfo(BaseModel):
    code: str
    name: str
    group: str
    assigned: bool = False
    endpoint: str = ""

    model_config = ConfigDict(from_attributes=True)


class RoleResponse(BaseModel):
    role_name: str
    permissions: list[PermissionInfo]

    model_config = ConfigDict(from_attributes=True)


class RoleListItem(BaseModel):
    role_name: str
    permission_count: int
    user_count: int

    model_config = ConfigDict(from_attributes=True)


class RoleListResponse(BaseModel):
    roles: list[RoleListItem]


class PermissionsListResponse(BaseModel):
    permissions: list[PermissionInfo]


class UpdateRolePermissionsRequest(BaseModel):
    permission_codes: list[str]

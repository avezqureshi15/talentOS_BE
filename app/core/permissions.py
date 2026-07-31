from __future__ import annotations

from enum import Enum


class Permission(str, Enum):
    APPLICATION_VIEW = "application.view"
    APPLICATION_EVALUATE = "application.evaluate"
    APPLICATION_REJECT = "application.reject"
    HIRING_REQUEST_CREATE = "hiring_request.create"
    HIRING_REQUEST_EDIT = "hiring_request.edit"
    HIRING_REQUEST_VIEW = "hiring_request.view"
    HIRING_REQUEST_DELETE = "hiring_request.delete"
    USER_INVITE = "user.invite"
    USER_MANAGE = "user.manage"
    TENANT_VIEW = "tenant.view"
    TENANT_EDIT = "tenant.edit"
    API_KEY_MANAGE = "api_key.manage"
    SETTINGS_VIEW = "settings.view"
    SETTINGS_EDIT = "settings.edit"
    SLOT_SUBMIT = "slot.submit"
    SLOT_VIEW_ALL = "slot.view_all"
    REVIEW_SUBMIT = "review.submit"
    REVIEW_VIEW_ALL = "review.view_all"
    CHAT = "chat"


DEFAULT_ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    "superadmin": set(Permission),
    "admin": {
        Permission.APPLICATION_VIEW,
        Permission.APPLICATION_EVALUATE,
        Permission.APPLICATION_REJECT,
        Permission.HIRING_REQUEST_CREATE,
        Permission.HIRING_REQUEST_EDIT,
        Permission.HIRING_REQUEST_VIEW,
        Permission.HIRING_REQUEST_DELETE,
        Permission.USER_INVITE,
        Permission.USER_MANAGE,
        Permission.API_KEY_MANAGE,
        Permission.SETTINGS_VIEW,
        Permission.SETTINGS_EDIT,
        Permission.SLOT_VIEW_ALL,
        Permission.REVIEW_SUBMIT,
        Permission.REVIEW_VIEW_ALL,
        Permission.CHAT,
    },
    "hr": {
        Permission.APPLICATION_VIEW,
        Permission.APPLICATION_EVALUATE,
        Permission.APPLICATION_REJECT,
        Permission.HIRING_REQUEST_CREATE,
        Permission.HIRING_REQUEST_EDIT,
        Permission.HIRING_REQUEST_VIEW,
        Permission.USER_INVITE,
        Permission.SLOT_VIEW_ALL,
        Permission.REVIEW_SUBMIT,
        Permission.REVIEW_VIEW_ALL,
        Permission.CHAT,
    },
    "viewer": {
        Permission.APPLICATION_VIEW,
        Permission.HIRING_REQUEST_VIEW,
        Permission.CHAT,
    },
}

PERMISSION_ENDPOINTS: dict[str, str] = {
    Permission.APPLICATION_VIEW.value: "GET /api/v1/applications",
    Permission.APPLICATION_EVALUATE.value: "POST /api/v1/evaluations/evaluate-async",
    Permission.APPLICATION_REJECT.value: "POST /api/v1/rounds/{round_id}/reject",
    Permission.HIRING_REQUEST_CREATE.value: "POST /api/v1/hiring-requests",
    Permission.HIRING_REQUEST_EDIT.value: "PUT /api/v1/hiring-requests/{id}",
    Permission.HIRING_REQUEST_VIEW.value: "GET /api/v1/hiring-requests, GET /api/v1/hiring-requests/{id}",
    Permission.HIRING_REQUEST_DELETE.value: "DELETE /api/v1/hiring-requests/{id}",
    Permission.USER_INVITE.value: "POST /api/v1/admin/users/invites",
    Permission.USER_MANAGE.value: "PATCH /api/v1/admin/users/{user_id}",
    Permission.TENANT_VIEW.value: "GET /api/v1/superadmin/tenants",
    Permission.TENANT_EDIT.value: "PATCH /api/v1/superadmin/tenants/{tenant_id}",
    Permission.API_KEY_MANAGE.value: "GET /api/v1/admin/apps, POST /api/v1/admin/apps",
    Permission.SETTINGS_VIEW.value: "GET /api/v1/settings",
    Permission.SETTINGS_EDIT.value: "PATCH /api/v1/settings",
    Permission.SLOT_SUBMIT.value: "POST /api/v1/slots",
    Permission.SLOT_VIEW_ALL.value: "GET /api/v1/slots/employee",
    Permission.REVIEW_SUBMIT.value: "POST /api/v1/reviews",
    Permission.REVIEW_VIEW_ALL.value: "GET /api/v1/reviews/round/{round_id}",
    Permission.CHAT.value: "GET /api/v1/chat/chats",
}

PERMISSION_META: dict[str, dict[str, str]] = {
    permission.value: {
        "name": " ".join(w.capitalize() for w in permission.value.split(".")),
        "group": permission.value.split(".")[0],
        "endpoint": PERMISSION_ENDPOINTS.get(permission.value, ""),
    }
    for permission in Permission
}

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

PERMISSION_META: dict[str, dict[str, str]] = {
    permission.value: {
        "name": " ".join(w.capitalize() for w in permission.value.split(".")),
        "group": permission.value.split(".")[0],
    }
    for permission in Permission
}

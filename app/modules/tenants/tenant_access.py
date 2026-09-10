"""Tenant lock checks shared by auth and API-key validation."""

from app.modules.tenants.tenant_model import Tenant

ORG_DELETED_MSG = "Your organization is permanently deleted."
ORG_SUSPENDED_MSG = "Your organization is suspended."
ORG_UNVERIFIED_MSG = "Your organization is not yet verified. Please contact support."


def tenant_lock_message(tenant: Tenant | None, *, check_verification: bool = False) -> str | None:
    if tenant is None:
        return None
    if tenant.deleted_at is not None:
        return ORG_DELETED_MSG
    if check_verification and tenant.verification_status != "approved":
        return ORG_UNVERIFIED_MSG
    # Pending/rejected orgs are also is_active=false; suspend only applies after approval.
    if not tenant.is_active and tenant.verification_status == "approved":
        return ORG_SUSPENDED_MSG
    return None

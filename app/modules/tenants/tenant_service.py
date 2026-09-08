from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.core.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.common.services.invite_email import send_invite_email
from app.modules.tenants.tenant_model import Tenant
from app.modules.tenants.tenant_repository import TenantRepository
from app.modules.tenants.tenant_schema import TenantResponse, PaginatedTenantResponse, TenantAdminDetails
from app.modules.users.user_model import User

logger = get_logger(__name__)

# A tenant shows as "inactive" on the tenant board once this many days have
# passed since its most recent user login (or since creation, if no user has
# ever logged in).
TENANT_INACTIVITY_THRESHOLD_DAYS = 30


class TenantError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class TenantService:
    def __init__(self, db: Session):
        self.repo = TenantRepository(db)
        self.db = db

    def _slugify(self, name: str) -> str:
        slug = name.lower().replace(" ", "-").replace("--", "-")[:80]
        base = slug
        counter = 1
        while self.repo.get_by_slug(slug):
            slug = f"{base}-{counter}"
            counter += 1
        return slug

    def _tenant_to_response(self, tenant: Tenant, viewer_user_id: int | None = None) -> TenantResponse:
        last_active_at = self.repo.get_last_login_at(tenant.id) or tenant.created_at
        is_inactive = (
            datetime.now(timezone.utc) - last_active_at
            > timedelta(days=TENANT_INACTIVITY_THRESHOLD_DAYS)
        )
        return TenantResponse(
            id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
            is_active=tenant.is_active,
            verification_status=tenant.verification_status,
            # Same privacy scoping as GET /admin/users — superadmin only sees
            # a count of users they personally created/invited, not the
            # tenant's full org-managed headcount.
            user_count=self.repo.count_users(tenant.id, created_by_user_id=viewer_user_id),
            employee_count=self.repo.count_employees(tenant.id),
            logo_url=tenant.logo_url,
            website=tenant.website,
            phone=tenant.phone,
            description=tenant.description,
            address_line1=tenant.address_line1,
            address_line2=tenant.address_line2,
            city=tenant.city,
            state=tenant.state,
            postal_code=tenant.postal_code,
            country=tenant.country,
            gst_number=tenant.gst_number,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at,
            last_active_at=last_active_at,
            is_inactive=is_inactive,
        )

    def create_tenant(
        self, org_name: str, admin_name: str, admin_email: str, invited_by_user_id: int
    ) -> TenantAdminDetails:
        existing_user = self.db.query(User).filter(User.email == admin_email).first()
        if existing_user:
            raise TenantError("A user with this email already exists")

        slug = self._slugify(org_name)
        tenant = self.repo.create_tenant(org_name, slug)

        invite = self.repo.create_invite(
            tenant_id=tenant.id,
            email=admin_email,
            role="account_admin",
            invited_by_user_id=invited_by_user_id,
        )

        self.db.commit()

        try:
            inviter = self.db.query(User).filter(User.id == invited_by_user_id).first()
            send_invite_email(
                admin_email,
                invite.token,
                organization_name=tenant.name,
                inviter_name=inviter.name if inviter else None,
            )
        except Exception as exc:
            logger.warning("Failed to send tenant invite email to %s: %s", admin_email, exc)

        return TenantAdminDetails(
            tenant_id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
            admin_email=admin_email,
            admin_name=admin_name,
            invite_token=invite.token,
            expires_at=invite.expires_at.isoformat(),
        )

    def list_tenants(
        self,
        page: int = 1,
        per_page: int = DEFAULT_PAGE_SIZE,
        search: str | None = None,
        status_filter: str | None = None,
        viewer_user_id: int | None = None,
    ) -> PaginatedTenantResponse:
        if per_page > MAX_PAGE_SIZE:
            per_page = MAX_PAGE_SIZE

        tenants, total = self.repo.list_tenants(page, per_page, search, status_filter)
        data = [self._tenant_to_response(t, viewer_user_id) for t in tenants]
        has_more = (page * per_page) < total

        return PaginatedTenantResponse(
            data=data,
            total=total,
            page=page,
            per_page=per_page,
            has_more=has_more,
        )

    def get_tenant(self, tenant_id: int, viewer_user_id: int | None = None) -> TenantResponse:
        tenant = self.repo.get_by_id(tenant_id)
        if not tenant:
            raise TenantError("Tenant not found", status_code=404)
        return self._tenant_to_response(tenant, viewer_user_id)

    def update_tenant(self, tenant_id: int, data: dict, viewer_user_id: int | None = None) -> TenantResponse:
        tenant = self.repo.get_by_id(tenant_id)
        if not tenant:
            raise TenantError("Tenant not found", status_code=404)

        self.repo.update_tenant(tenant, data)
        self.db.commit()
        self.db.refresh(tenant)
        return self._tenant_to_response(tenant, viewer_user_id)

    def delete_tenant(self, tenant_id: int) -> None:
        tenant = self.repo.get_by_id(tenant_id)
        if not tenant:
            raise TenantError("Tenant not found", status_code=404)

        self.repo.delete_tenant(tenant)
        self.db.commit()
        logger.info("Tenant soft-deleted: id=%d", tenant_id)

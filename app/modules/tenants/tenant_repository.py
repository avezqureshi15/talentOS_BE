import secrets
from datetime import datetime, timezone, timedelta
from typing import Sequence

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.modules.tenants.tenant_model import Tenant
from app.modules.auth.invite_model import TenantInvite

logger = get_logger(__name__)

INVITE_EXPIRE_DAYS = 7


class TenantRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, tenant_id: int) -> Tenant | None:
        return self.db.query(Tenant).filter(Tenant.id == tenant_id).first()

    def get_by_slug(self, slug: str) -> Tenant | None:
        return self.db.query(Tenant).filter(Tenant.slug == slug).first()

    def create_tenant(self, name: str, slug: str) -> Tenant:
        tenant = Tenant(
            name=name,
            slug=slug,
            is_active=True,
            verification_status="approved",
        )
        self.db.add(tenant)
        self.db.flush()
        logger.info("Created tenant: id=%d slug=%s", tenant.id, slug)
        return tenant

    def list_tenants(
        self,
        page: int,
        per_page: int,
        search: str | None = None,
        status_filter: str | None = None,
    ) -> tuple[Sequence[Tenant], int]:
        query = self.db.query(Tenant)

        if search:
            query = query.filter(
                or_(
                    Tenant.name.ilike(f"%{search}%"),
                    Tenant.slug.ilike(f"%{search}%"),
                )
            )

        if status_filter:
            if status_filter == "active":
                query = query.filter(Tenant.is_active == True)
            elif status_filter == "suspended":
                query = query.filter(Tenant.is_active == False)
            elif status_filter:
                query = query.filter(Tenant.verification_status == status_filter)

        total = query.count()
        tenants = (
            query.order_by(Tenant.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return tenants, total

    def update_tenant(self, tenant: Tenant, data: dict) -> Tenant:
        for key, value in data.items():
            if value is not None:
                setattr(tenant, key, value)
        self.db.flush()
        logger.info("Updated tenant: id=%d", tenant.id)
        return tenant

    def delete_tenant(self, tenant: Tenant) -> None:
        tenant.is_active = False
        self.db.flush()
        logger.info("Soft-deleted tenant: id=%d", tenant.id)

    def create_invite(
        self,
        tenant_id: int,
        email: str,
        role: str,
        invited_by_user_id: int,
    ) -> TenantInvite:
        token = secrets.token_urlsafe(48)
        expires_at = datetime.now(timezone.utc) + timedelta(days=INVITE_EXPIRE_DAYS)
        invite = TenantInvite(
            tenant_id=tenant_id,
            email=email,
            role=role,
            token=token,
            invited_by_user_id=invited_by_user_id,
            expires_at=expires_at,
        )
        self.db.add(invite)
        self.db.flush()
        logger.info("Created invite for tenant_id=%d email=%s", tenant_id, email)
        return invite

    def count_users(self, tenant_id: int) -> int:
        from app.modules.users.user_model import User

        return (
            self.db.query(func.count(User.id))
            .filter(User.tenant_id == tenant_id)
            .scalar()
            or 0
        )

    def count_employees(self, tenant_id: int) -> int:
        from app.modules.employees.employee_model import Employee

        return (
            self.db.query(func.count(Employee.id))
            .filter(Employee.tenant_id == tenant_id)
            .scalar()
            or 0
        )

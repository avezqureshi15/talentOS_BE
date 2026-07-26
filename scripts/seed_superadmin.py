"""Insert a superadmin user directly into the database.
Usage: python scripts/seed_superadmin.py
"""
import sys
sys.path.insert(0, ".")

from datetime import datetime, timezone
from app.db.session import SessionLocal
from app.modules.tenants.tenant_model import Tenant
from app.modules.users.user_model import User
from app.core.security import hash_password

EMAIL = "superadmin@talentos.com"
PASSWORD = "superadmin123"
NAME = "Super Admin"


def main():
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == EMAIL).first()
        if existing:
            print(f"User {EMAIL} already exists (id={existing.id}, role={existing.role})")
            return

        tenant = db.query(Tenant).first()
        if not tenant:
            tenant = Tenant(
                name="Platform",
                slug="platform",
                is_active=True,
                verification_status="approved",
            )
            db.add(tenant)
            db.flush()
            print(f"Created tenant: id={tenant.id}")

        now = datetime.now(timezone.utc)
        user = User(
            emp_id=f"u_superadmin",
            email=EMAIL,
            name=NAME,
            password_hash=hash_password(PASSWORD),
            auth_provider="email",
            tenant_id=tenant.id,
            role="superadmin",
            is_active=True,
            status="active",
            user_type="employee",
            designation="Super Admin",
            department="Platform",
            work_mode="remote",
            delivery_status="active",
            work_location_type="remote",
            doj=now.date(),
            date_of_birth=now.date(),
            band="L1",
        )
        db.add(user)
        db.commit()
        print(f"Superadmin created: email={EMAIL} / password={PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

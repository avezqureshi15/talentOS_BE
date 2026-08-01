from datetime import date, datetime, timezone
from hashlib import sha256

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.modules.auth.auth_model import RefreshToken
from app.modules.users.user_model import User

logger = get_logger(__name__)


class AuthRepository:
    def __init__(self, db: Session):
        self.db = db

    # ── User ──────────────────────────────────────────────────────

    def get_user_by_email(self, email: str) -> User | None:
        return self.db.execute(
            select(User).where(User.email == email)
        ).scalar_one_or_none()

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.db.execute(
            select(User).where(User.id == user_id)
        ).scalar_one_or_none()

    def create_user(
        self,
        emp_id: str,
        email: str,
        name: str,
        commit: bool = True,
        **extra: dict,
    ) -> User:
        now = datetime.now(timezone.utc)
        defaults = {
            "status": "active",
            "user_type": "employee",
            "designation": "Unassigned",
            "department": "Unassigned",
            "role": "recruiter",
            "work_mode": "remote",
            "delivery_status": "active",
            "work_location_type": "remote",
            "doj": now.date(),
            "date_of_birth": now.date(),
            "band": "L1",
            "auth_provider": "google",
        }
        defaults.update(extra)
        user = User(
            emp_id=emp_id,
            email=email,
            name=name,
            **defaults,
        )
        self.db.add(user)
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        logger.info("Created user: email=%s id=%d", email, user.id)
        return user

    # ── Refresh Token ─────────────────────────────────────────────

    def create_refresh_token(
        self, token_hash: str, user_id: int, expires_at: datetime,
    ) -> RefreshToken:
        record = RefreshToken(
            token_hash=token_hash,
            user_id=user_id,
            expires_at=expires_at,
        )
        self.db.add(record)
        self.db.flush()
        logger.debug("Created refresh token for user_id=%d", user_id)
        return record

    def get_refresh_token_by_hash(self, token_hash: str) -> RefreshToken | None:
        return self.db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.expires_at > datetime.now(timezone.utc),
            ),
        ).scalar_one_or_none()

    def delete_refresh_token_by_hash(self, token_hash: str) -> None:
        self.db.execute(
            delete(RefreshToken).where(RefreshToken.token_hash == token_hash),
        )
        self.db.commit()

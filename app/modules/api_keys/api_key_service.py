import hashlib
import secrets
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.core.permissions import PERMISSION_META
from app.modules.api_keys.api_key_model import ApiKey, ApiKeyPermission
from app.modules.api_keys.api_key_schema import (
    ApiKeyCreatedResponse,
    ApiKeyDetailResponse,
    ApiKeyListResponse,
    ApiKeyResponse,
    PermissionInfo,
)
from app.modules.users.permission_model import PermissionModel

logger = get_logger(__name__)

API_KEY_PREFIX = "tal_"
KEY_BYTES = 48


def _generate_api_key() -> tuple[str, str, str]:
    raw = secrets.token_urlsafe(KEY_BYTES)
    full_key = f"{API_KEY_PREFIX}{raw}"
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    key_prefix = full_key[:8]
    return full_key, key_hash, key_prefix


class ApiKeyService:
    def __init__(self, db: Session):
        self.db = db

    def create_app(self, name: str, description: str | None, created_by_user_id: int) -> ApiKeyCreatedResponse:
        full_key, key_hash, key_prefix = _generate_api_key()
        now = datetime.now(timezone.utc)
        api_key = ApiKey(
            name=name,
            description=description,
            key_hash=key_hash,
            key_prefix=key_prefix,
            created_by_user_id=created_by_user_id,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self.db.add(api_key)
        self.db.flush()

        default_perms = self.db.execute(
            select(PermissionModel.code).where(PermissionModel.is_default == True)
        ).scalars().all()

        if default_perms:
            for code in default_perms:
                self.db.add(ApiKeyPermission(api_key_id=api_key.id, permission_code=code))
        else:
            for code in PERMISSION_META:
                self.db.add(ApiKeyPermission(api_key_id=api_key.id, permission_code=code))

        self.db.commit()
        self.db.refresh(api_key)
        logger.info("Created API app: id=%d name=%s by user_id=%d", api_key.id, name, created_by_user_id)
        return ApiKeyCreatedResponse(
            id=api_key.id,
            name=api_key.name,
            description=api_key.description,
            key_prefix=api_key.key_prefix,
            is_active=api_key.is_active,
            expires_at=api_key.expires_at,
            last_used_at=api_key.last_used_at,
            created_at=api_key.created_at,
            full_key=full_key,
        )

    def list_apps(self, page: int, per_page: int, search: str | None = None) -> ApiKeyListResponse:
        query = select(ApiKey).order_by(ApiKey.created_at.desc())
        count_query = select(func.count(ApiKey.id))

        if search:
            query = query.where(ApiKey.name.ilike(f"%{search}%"))
            count_query = count_query.where(ApiKey.name.ilike(f"%{search}%"))

        total = self.db.execute(count_query).scalar() or 0
        offset = (page - 1) * per_page
        rows = self.db.execute(query.offset(offset).limit(per_page)).scalars().all()

        data = [
            ApiKeyResponse(
                id=r.id,
                name=r.name,
                description=r.description,
                key_prefix=r.key_prefix,
                is_active=r.is_active,
                expires_at=r.expires_at,
                last_used_at=r.last_used_at,
                created_at=r.created_at,
            )
            for r in rows
        ]
        has_more = (page * per_page) < total
        return ApiKeyListResponse(data=data, total=total, page=page, per_page=per_page, has_more=has_more)

    def get_app(self, app_id: int) -> ApiKeyDetailResponse | None:
        api_key = self.db.execute(select(ApiKey).where(ApiKey.id == app_id)).scalar_one_or_none()
        if not api_key:
            return None

        assigned_codes = self.db.execute(
            select(ApiKeyPermission.permission_code).where(ApiKeyPermission.api_key_id == app_id)
        ).scalars().all()
        assigned_set = set(assigned_codes)

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

        return ApiKeyDetailResponse(
            id=api_key.id,
            name=api_key.name,
            description=api_key.description,
            key_prefix=api_key.key_prefix,
            is_active=api_key.is_active,
            expires_at=api_key.expires_at,
            last_used_at=api_key.last_used_at,
            created_at=api_key.created_at,
            permissions=permissions,
        )

    def update_app(self, app_id: int, name: str | None, description: str | None) -> ApiKeyResponse | None:
        api_key = self.db.execute(select(ApiKey).where(ApiKey.id == app_id)).scalar_one_or_none()
        if not api_key:
            return None

        if name is not None:
            api_key.name = name
        if description is not None:
            api_key.description = description
        api_key.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(api_key)

        return ApiKeyResponse(
            id=api_key.id,
            name=api_key.name,
            description=api_key.description,
            key_prefix=api_key.key_prefix,
            is_active=api_key.is_active,
            expires_at=api_key.expires_at,
            last_used_at=api_key.last_used_at,
            created_at=api_key.created_at,
        )

    def revoke_app(self, app_id: int) -> bool:
        api_key = self.db.execute(select(ApiKey).where(ApiKey.id == app_id)).scalar_one_or_none()
        if not api_key:
            return False
        api_key.is_active = False
        api_key.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        logger.info("Revoked API app: id=%d", app_id)
        return True

    def rotate_key(self, app_id: int) -> ApiKeyCreatedResponse | None:
        api_key = self.db.execute(select(ApiKey).where(ApiKey.id == app_id)).scalar_one_or_none()
        if not api_key:
            return None

        full_key, key_hash, key_prefix = _generate_api_key()
        api_key.key_hash = key_hash
        api_key.key_prefix = key_prefix
        api_key.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(api_key)
        logger.info("Rotated API key: id=%d", app_id)

        return ApiKeyCreatedResponse(
            id=api_key.id,
            name=api_key.name,
            description=api_key.description,
            key_prefix=api_key.key_prefix,
            is_active=api_key.is_active,
            expires_at=api_key.expires_at,
            last_used_at=api_key.last_used_at,
            created_at=api_key.created_at,
            full_key=full_key,
        )

    def update_permissions(self, app_id: int, permission_codes: list[str]) -> ApiKeyDetailResponse | None:
        api_key = self.db.execute(select(ApiKey).where(ApiKey.id == app_id)).scalar_one_or_none()
        if not api_key:
            return None

        self.db.execute(
            delete(ApiKeyPermission).where(ApiKeyPermission.api_key_id == app_id)
        )

        for code in permission_codes:
            self.db.add(ApiKeyPermission(api_key_id=app_id, permission_code=code))

        self.db.commit()
        logger.info("Updated permissions for API app: id=%d codes=%s", app_id, permission_codes)
        return self.get_app(app_id)

    @staticmethod
    def validate_api_key(raw_key: str, db: Session) -> ApiKey | None:
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        api_key = db.execute(
            select(ApiKey).where(
                ApiKey.key_hash == key_hash,
                ApiKey.is_active == True,
            )
        ).scalar_one_or_none()

        if not api_key:
            return None

        if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
            return None

        api_key.last_used_at = datetime.now(timezone.utc)
        db.flush()
        return api_key

    @staticmethod
    def get_permissions_for_key(api_key_id: int, db: Session) -> list[str]:
        rows = db.execute(
            select(ApiKeyPermission.permission_code).where(
                ApiKeyPermission.api_key_id == api_key_id
            )
        ).scalars().all()

        if not rows:
            from app.core.permissions import Permission
            return sorted(p.value for p in Permission)

        return sorted(rows)

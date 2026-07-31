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
from app.modules.tenants.tenant_model import Tenant
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

    def _tenant_names(self, tenant_ids: set[int | None]) -> dict[int, str]:
        tenant_ids = {tid for tid in tenant_ids if tid is not None}
        if not tenant_ids:
            return {}
        rows = self.db.execute(
            select(Tenant.id, Tenant.name).where(Tenant.id.in_(tenant_ids))
        ).all()
        return {row.id: row.name for row in rows}

    def _api_key_to_response(self, key: ApiKey, tenant_names: dict[int, str]) -> ApiKeyResponse:
        return ApiKeyResponse(
            id=key.id,
            name=key.name,
            description=key.description,
            key_prefix=key.key_prefix,
            tenant_id=key.tenant_id,
            tenant_name=tenant_names.get(key.tenant_id) if key.tenant_id is not None else None,
            is_active=key.is_active,
            expires_at=key.expires_at,
            last_used_at=key.last_used_at,
            created_at=key.created_at,
        )

    def create_app(
        self,
        name: str,
        description: str | None,
        created_by_user_id: int,
        tenant_id: int | None,
    ) -> ApiKeyCreatedResponse:
        full_key, key_hash, key_prefix = _generate_api_key()
        now = datetime.now(timezone.utc)
        api_key = ApiKey(
            name=name,
            description=description,
            key_hash=key_hash,
            key_prefix=key_prefix,
            created_by_user_id=created_by_user_id,
            tenant_id=tenant_id,
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
        logger.info(
            "Created API app: id=%d name=%s by user_id=%d tenant_id=%s",
            api_key.id,
            name,
            created_by_user_id,
            tenant_id,
        )
        tenant_names = self._tenant_names({api_key.tenant_id})
        response = self._api_key_to_response(api_key, tenant_names)
        return ApiKeyCreatedResponse(**response.model_dump(), full_key=full_key)

    def list_apps(
        self,
        page: int,
        per_page: int,
        search: str | None = None,
        tenant_id: int | None = None,
    ) -> ApiKeyListResponse:
        query = select(ApiKey).order_by(ApiKey.created_at.desc())
        count_query = select(func.count(ApiKey.id))

        if tenant_id is not None:
            query = query.where(ApiKey.tenant_id == tenant_id)
            count_query = count_query.where(ApiKey.tenant_id == tenant_id)

        if search:
            query = query.where(ApiKey.name.ilike(f"%{search}%"))
            count_query = count_query.where(ApiKey.name.ilike(f"%{search}%"))

        total = self.db.execute(count_query).scalar() or 0
        offset = (page - 1) * per_page
        rows = self.db.execute(query.offset(offset).limit(per_page)).scalars().all()

        tenant_names = self._tenant_names({r.tenant_id for r in rows})
        data = [self._api_key_to_response(r, tenant_names) for r in rows]
        has_more = (page * per_page) < total
        return ApiKeyListResponse(data=data, total=total, page=page, per_page=per_page, has_more=has_more)

    def _get_scoped(self, app_id: int, tenant_id: int | None) -> ApiKey | None:
        query = select(ApiKey).where(ApiKey.id == app_id)
        if tenant_id is not None:
            query = query.where(ApiKey.tenant_id == tenant_id)
        return self.db.execute(query).scalar_one_or_none()

    def get_app(self, app_id: int, tenant_id: int | None = None) -> ApiKeyDetailResponse | None:
        api_key = self._get_scoped(app_id, tenant_id)
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

        tenant_names = self._tenant_names({api_key.tenant_id})
        response = self._api_key_to_response(api_key, tenant_names)
        return ApiKeyDetailResponse(**response.model_dump(), permissions=permissions)

    def update_app(
        self,
        app_id: int,
        name: str | None,
        description: str | None,
        tenant_id: int | None = None,
    ) -> ApiKeyResponse | None:
        api_key = self._get_scoped(app_id, tenant_id)
        if not api_key:
            return None

        if name is not None:
            api_key.name = name
        if description is not None:
            api_key.description = description
        api_key.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(api_key)

        tenant_names = self._tenant_names({api_key.tenant_id})
        return self._api_key_to_response(api_key, tenant_names)

    def revoke_app(self, app_id: int, tenant_id: int | None = None) -> bool:
        api_key = self._get_scoped(app_id, tenant_id)
        if not api_key:
            return False
        api_key.is_active = False
        api_key.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        logger.info("Revoked API app: id=%d", app_id)
        return True

    def rotate_key(self, app_id: int, tenant_id: int | None = None) -> ApiKeyCreatedResponse | None:
        api_key = self._get_scoped(app_id, tenant_id)
        if not api_key:
            return None

        full_key, key_hash, key_prefix = _generate_api_key()
        api_key.key_hash = key_hash
        api_key.key_prefix = key_prefix
        api_key.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(api_key)
        logger.info("Rotated API key: id=%d", app_id)

        tenant_names = self._tenant_names({api_key.tenant_id})
        response = self._api_key_to_response(api_key, tenant_names)
        return ApiKeyCreatedResponse(**response.model_dump(), full_key=full_key)

    def update_permissions(
        self,
        app_id: int,
        permission_codes: list[str],
        tenant_id: int | None = None,
    ) -> ApiKeyDetailResponse | None:
        api_key = self._get_scoped(app_id, tenant_id)
        if not api_key:
            return None

        self.db.execute(
            delete(ApiKeyPermission).where(ApiKeyPermission.api_key_id == app_id)
        )

        for code in permission_codes:
            self.db.add(ApiKeyPermission(api_key_id=app_id, permission_code=code))

        self.db.commit()
        logger.info("Updated permissions for API app: id=%d codes=%s", app_id, permission_codes)
        return self.get_app(app_id, tenant_id=tenant_id)

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

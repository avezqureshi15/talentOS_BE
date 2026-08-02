"""Tenant-context middleware — publishes the authenticated user's tenant_id
into a ContextVar so deep callers (e.g. secret lookup) can resolve it without
threading the request through every layer.
"""

import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.config import settings
from app.core.logger import get_logger
from app.core.secrets import current_tenant_id

logger = get_logger(__name__)


class TenantContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        tenant_id: int | None = None
        authorization = request.headers.get("Authorization")
        if authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]
            try:
                payload = jwt.decode(token, options={"verify_signature": False})
                raw = payload.get("tenant_id")
                tenant_id = int(raw) if raw is not None else None
            except (ValueError, TypeError, jwt.PyJWTError):
                tenant_id = None
        token_cv = current_tenant_id.set(tenant_id)
        try:
            response = await call_next(request)
        finally:
            current_tenant_id.reset(token_cv)
        return response

"""Origin-capture middleware — records the public frontend origin seen on
incoming requests (scheme + host from ``X-Forwarded-Proto`` / ``Host`` via
uvicorn proxy headers) so background mail tasks and cron jobs can build
correct absolute frontend links without a request context.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.frontend import set_last_origin


class OriginCaptureMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        set_last_origin(str(request.url))
        return await call_next(request)

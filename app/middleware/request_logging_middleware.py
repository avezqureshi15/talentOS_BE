import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.logger import get_logger
from app.core.security import generate_request_id

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = generate_request_id()
        request.state.request_id = request_id

        start_time = time.time()
        method = request.method
        path = request.url.path

        logger.info("IN  | %s %s | rid=%s", method, path, request_id)

        response = await call_next(request)

        elapsed = (time.time() - start_time) * 1000
        logger.info(
            "OUT | %s %s | status=%d | %.1fms | rid=%s",
            method,
            path,
            response.status_code,
            elapsed,
            request_id,
        )

        response.headers["X-Request-ID"] = request_id
        return response

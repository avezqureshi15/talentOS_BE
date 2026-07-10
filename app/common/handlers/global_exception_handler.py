import traceback

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.common.exceptions.base_exception import BaseAppException
from app.core.constants import ErrorCode
from app.core.logger import get_logger

logger = get_logger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(BaseAppException)
    async def base_app_exception_handler(request: Request, exc: BaseAppException) -> JSONResponse:
        logger.error(
            "App exception: %s | code=%s | path=%s",
            exc.message,
            exc.code.value,
            request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        logger.error("HTTP exception: %s | path=%s", exc.detail, request.url.path)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "code": ErrorCode.INTERNAL_ERROR.value,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "Unhandled exception: %s | path=%s\n%s",
            str(exc),
            request.url.path,
            traceback.format_exc(),
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "An internal error occurred",
                "code": ErrorCode.INTERNAL_ERROR.value,
            },
        )

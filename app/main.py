from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.common.handlers import register_exception_handlers
from app.core.config import settings
from app.core.logger import get_logger, setup_logging
from app.db.base import Base
from app.db.session import engine
from app.middleware import RequestLoggingMiddleware
from app.modules.applications import router as applications_router
from app.modules.designation import router as designation_router
from app.modules.jobs import router as jobs_router
from app.modules.todo import router as todo_router
from app.modules.users import router as users_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("Starting %s v%s | env=%s", settings.APP_NAME, settings.APP_VERSION, settings.APP_ENV)
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created")
    except Exception as exc:
        logger.warning("Database unavailable — running in proxy-only mode: %s", str(exc))
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(RequestLoggingMiddleware)
register_exception_handlers(app)
app.include_router(todo_router)
app.include_router(jobs_router)
app.include_router(applications_router)
app.include_router(designation_router)
app.include_router(users_router)


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}

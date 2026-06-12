from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.common.handlers import register_exception_handlers
from app.core.config import settings
from app.core.logger import get_logger, setup_logging
from app.db.base import Base
from app.db.session import engine
from app.middleware import RequestLoggingMiddleware
from app.modules.todo import router as todo_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("Starting %s v%s | env=%s", settings.APP_NAME, settings.APP_VERSION, settings.APP_ENV)
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")
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


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}

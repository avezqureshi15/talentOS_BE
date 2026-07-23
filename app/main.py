import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.common.handlers import register_exception_handlers
from app.core.config import settings
from app.core.kafka import ensure_topics
from app.core.logger import get_logger, setup_logging
from app.db.session import engine
from app.cron.hourly_jobs import setup_form_jobs
from app.middleware import RequestLoggingMiddleware
from app.scheduler import init_scheduler, shutdown_scheduler
from app.modules.applications import router as applications_router
from app.modules.alerts import router as alerts_router
from app.modules.auth.auth_router import router as auth_router
from app.modules.chat.chat_router import router as chat_router
from app.modules.designation import router as designation_router
from app.modules.email.email_router import router as email_router
from app.modules.events import router as events_router
from app.modules.employees import router as employees_router
from app.modules.evaluations import candidates_router as evaluation_candidates_router
from app.modules.evaluations import router as evaluations_router
from app.modules.forms import ask_router, form_router
from app.modules.hiring_requests import router as hiring_requests_router
from app.modules.interviews import router as interviews_router
from app.modules.reviews import router as reviews_router
from app.modules.rounds import router as rounds_router
from app.modules.jobs import router as jobs_router
from app.modules.slots import router as slots_router
from app.modules.todo import router as todo_router
from app.modules.settings.settings_router import router as settings_router
from app.modules.users import router as users_router
from app.modules.users.user_admin_router import router as user_admin_router

logger = get_logger(__name__)


def run_migrations():
    alembic_dir = Path(__file__).resolve().parent.parent / "alembic"
    if not (alembic_dir / "alembic.ini").exists():
        logger.warning("alembic.ini not found, skipping auto-migration")
        return
    try:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=alembic_dir.parent,
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            logger.info("Migrations up to date")
        else:
            logger.error("Migration failed: %s", result.stderr)
    except Exception as exc:
        logger.error("Migration error: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("Starting %s v%s | env=%s", settings.APP_NAME, settings.APP_VERSION, settings.APP_ENV)
    run_migrations()
    ensure_topics()
    scheduler = init_scheduler()
    setup_form_jobs(scheduler)
    yield
    shutdown_scheduler()
    engine.dispose()
    logger.info("Shutting down %s", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(RequestLoggingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOW_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_exception_handlers(app)
app.include_router(auth_router)
app.include_router(todo_router)
app.include_router(jobs_router)
app.include_router(applications_router)
app.include_router(chat_router)
app.include_router(designation_router)
app.include_router(events_router)
app.include_router(hiring_requests_router)
app.include_router(interviews_router)
app.include_router(reviews_router)
app.include_router(rounds_router)
app.include_router(slots_router)
app.include_router(ask_router)
app.include_router(form_router)
app.include_router(alerts_router)
app.include_router(employees_router)
app.include_router(users_router)
app.include_router(evaluations_router)
app.include_router(evaluation_candidates_router)
app.include_router(email_router)
app.include_router(user_admin_router)
app.include_router(settings_router)


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}

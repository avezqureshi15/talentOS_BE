import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.common.handlers import register_exception_handlers
from google.auth.transport import requests as google_requests

from app.core.config import settings
from app.core.kafka import ensure_topics
from app.core.logger import get_logger, setup_logging
from app.db.session import engine
from app.cron.hourly_jobs import setup_form_jobs
from app.middleware import RequestLoggingMiddleware, TenantContextMiddleware
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
from app.modules.evaluations import webhook_router as evaluation_webhook_router
from app.modules.evaluations import router as evaluations_router
from app.modules.forms import ask_router, form_router
from app.modules.hiring_requests import router as hiring_requests_router
from app.modules.hiring_requests.hiring_request_internal_router import router as hiring_requests_internal_router
from app.modules.hiring_requests.hiring_request_export_router import router as hiring_requests_export_router
from app.modules.hiring_requests.hiring_request_import_router import router as hiring_requests_import_router
from app.modules.hiring_requests.ai_integration_router import router as ai_integration_router
from app.modules.ai.ai_generate_router import router as ai_generate_router
from app.modules.interview_designs.interview_design_router import router as interview_designs_router
from app.core.internal_router import router as internal_router
from app.modules.interviews import router as interviews_router
from app.modules.interviews.meetmind_webhook_router import router as meetmind_webhook_router
from app.modules.job_teams.job_team_router import router as job_teams_router
from app.modules.reviews import router as reviews_router
from app.modules.rounds import router as rounds_router
from app.modules.jobs import router as jobs_router
from app.modules.slots import router as slots_router
from app.modules.todo import router as todo_router
from app.modules.settings.settings_router import router as settings_router
from app.modules.users import router as users_router
from app.modules.users.user_admin_router import router as user_admin_router
from app.modules.api_keys.api_key_router import router as api_key_router
from app.modules.api_keys.api_key_admin_router import router as api_key_admin_router
from app.modules.tenants.tenant_router import router as tenant_router
from app.modules.tenants.org_router import router as org_router
from app.modules.roles.role_router import router as role_router

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
    ensure_topics([
        (settings.KAFKA_TOPIC_EVALUATION_ASYNC, settings.KAFKA_EVALUATION_PARTITIONS),
        (settings.KAFKA_TOPIC_EVALUATION_ASYNC_DLQ, 1),
    ])
    scheduler = init_scheduler()
    setup_form_jobs(scheduler)

    try:
        _ = google_requests.Request()
        logger.info("Google auth session warmed up")
    except Exception as exc:
        logger.warning("Google auth session warm-up failed: %s", exc)

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
app.add_middleware(TenantContextMiddleware)

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
app.include_router(hiring_requests_export_router)
app.include_router(hiring_requests_import_router)
app.include_router(interviews_router)
app.include_router(meetmind_webhook_router)
app.include_router(reviews_router)
app.include_router(rounds_router)
app.include_router(slots_router)
app.include_router(ask_router)
app.include_router(form_router)
app.include_router(alerts_router)
app.include_router(employees_router)
app.include_router(users_router)
app.include_router(evaluation_webhook_router)
app.include_router(evaluations_router)
app.include_router(evaluation_candidates_router)
app.include_router(email_router)
app.include_router(user_admin_router)
app.include_router(settings_router)
app.include_router(tenant_router)
app.include_router(api_key_router)
app.include_router(api_key_admin_router)
app.include_router(org_router)
app.include_router(role_router)
app.include_router(job_teams_router)

app.include_router(hiring_requests_internal_router, prefix="/internal")
app.include_router(ai_integration_router)
app.include_router(ai_generate_router)
app.include_router(interview_designs_router)
app.include_router(internal_router)


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}

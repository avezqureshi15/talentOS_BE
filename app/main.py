from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.cron import run_hourly_jobs_forever
from app.common.handlers import register_exception_handlers
from app.core.config import settings
from app.core.kafka import ensure_topics
from app.core.logger import get_logger, setup_logging
from app.middleware import RequestLoggingMiddleware
from app.modules.applications import router as applications_router
from app.modules.alerts import router as alerts_router
from app.modules.auth.auth_router import router as auth_router
from app.modules.chat.chat_router import router as chat_router
from app.modules.designation import router as designation_router
from app.modules.email.email_router import router as email_router
from app.modules.employees import router as employees_router
from app.modules.evaluations import candidates_router as evaluation_candidates_router
from app.modules.evaluations import router as evaluations_router
from app.modules.forms import ask_router, form_router
from app.modules.hiring_requests import router as hiring_requests_router
from app.modules.interviews import router as interviews_router
from app.modules.jobs import router as jobs_router
from app.modules.slots import router as slots_router
from app.modules.todo import router as todo_router
from app.modules.users import router as users_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("Starting %s v%s | env=%s", settings.APP_NAME, settings.APP_VERSION, settings.APP_ENV)
    ensure_topics()
    cron_stop_event = asyncio.Event()
    cron_task = asyncio.create_task(run_hourly_jobs_forever(cron_stop_event))
    yield
    cron_stop_event.set()
    await cron_task
    logger.info("Shutting down %s", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(RequestLoggingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:4173"],
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
app.include_router(hiring_requests_router)
app.include_router(interviews_router)
app.include_router(slots_router)
app.include_router(ask_router)
app.include_router(form_router)
app.include_router(alerts_router)
app.include_router(employees_router)
app.include_router(users_router)
app.include_router(evaluations_router)
app.include_router(evaluation_candidates_router)
app.include_router(email_router)


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}

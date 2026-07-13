from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_MISSED, EVENT_JOB_MAX_INSTANCES
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler

from app.core.logger import get_logger
from app.db.session import engine

_scheduler: BackgroundScheduler | None = None
logger = get_logger(__name__)


JOB_DESCRIPTIONS: dict[str, str] = {
    "form_reminder": "Sends follow-up emails to interviewers who haven't submitted their review forms",
    "form_escalation": "Escalates overdue review forms to the next level (manager or alternate)",
    "form_expiry": "Marks review/slot forms that have exceeded the expiry window as expired",
}


def _get_job_info(job_id: str) -> str:
    desc = JOB_DESCRIPTIONS.get(job_id, "")
    return f"name=\"{job_id}\" description=\"{desc}\"" if desc else f"name=\"{job_id}\""


def _log_job_event(event) -> None:
    mapping = {
        EVENT_JOB_ERROR: ("Job errored", "errored"),
        EVENT_JOB_MISSED: ("Job missed", "missed"),
        EVENT_JOB_MAX_INSTANCES: ("Job max instances reached", "max_instances"),
    }
    msg, _ = mapping.get(event.code, ("Job event", str(event.code)))
    logger.warning("%s | %s scheduled_run_time=%s exception=%s", msg, _get_job_info(event.job_id), getattr(event, "scheduled_run_time", None), getattr(event, "exception", None))


def _register_listeners(scheduler: BackgroundScheduler) -> None:
    scheduler.add_listener(
        _log_job_event,
        EVENT_JOB_ERROR | EVENT_JOB_MISSED | EVENT_JOB_MAX_INSTANCES,
    )


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        raise RuntimeError("Scheduler not initialized. Call init_scheduler first.")
    return _scheduler


def init_scheduler() -> BackgroundScheduler:
    global _scheduler
    jobstore = SQLAlchemyJobStore(engine=engine)
    _scheduler = BackgroundScheduler(
        jobstores={"default": jobstore},
        timezone="UTC",
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 1800,
        },
    )
    _register_listeners(_scheduler)
    _scheduler.start()
    logger.info("Scheduler started | jobstore=sqlalchemy timezone=UTC")
    return _scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler:
        jobs = _scheduler.get_jobs()
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler shut down | pending_jobs=%d", len(jobs))
        _scheduler = None

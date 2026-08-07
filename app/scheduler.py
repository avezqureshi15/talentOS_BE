from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_MISSED, EVENT_JOB_MAX_INSTANCES
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.exc import OperationalError

from app.core.logger import get_logger
from app.db.session import engine

_scheduler: BackgroundScheduler | None = None
logger = get_logger(__name__)


class ResilientSQLAlchemyJobStore(SQLAlchemyJobStore):
    """SQLAlchemy jobstore whose DB failures never kill the scheduler thread.

    APSScheduler guards ``get_due_jobs()`` but not ``get_next_run_time()`` or
    ``update_job()`` in ``_process_jobs``, so a transient DB error (dropped
    pooled connection, server restart) escapes and the whole cron thread dies.
    This store disposes the connection pool and retries a failed query once;
    if the DB is still unreachable it degrades gracefully (empty results,
    skipped writes) instead of raising, so the scheduler keeps running and
    resumes normally once connectivity returns.
    """

    def _run(self, fn, default, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except OperationalError:
            logger.warning(
                "Jobstore DB error — disposing pool and retrying | op=%s", getattr(fn, "__name__", fn),
            )
            try:
                self.engine.dispose()
            except Exception:
                pass
            try:
                return fn(*args, **kwargs)
            except OperationalError:
                logger.error(
                    "Jobstore DB still unavailable — degrading | op=%s", getattr(fn, "__name__", fn),
                )
                return default

    def lookup_job(self, job_id):
        return self._run(super().lookup_job, None, job_id)

    def get_due_jobs(self, now):
        return self._run(super().get_due_jobs, [], now)

    def get_next_run_time(self):
        return self._run(super().get_next_run_time, None)

    def get_all_jobs(self):
        return self._run(super().get_all_jobs, [])

    def add_job(self, job):
        self._run(super().add_job, None, job)

    def update_job(self, job):
        self._run(super().update_job, None, job)

    def remove_job(self, job_id):
        self._run(super().remove_job, None, job_id)

    def remove_all_jobs(self):
        self._run(super().remove_all_jobs, None)


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
    jobstore = ResilientSQLAlchemyJobStore(engine=engine)
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
    _ensure_failed_jobs_table()

    logger.info("Scheduler initialized | jobstore=sqlalchemy timezone=UTC (not started)")
    return _scheduler


def start_scheduler() -> None:
    """Start the scheduler after all startup jobs have been registered.

    Jobs must be added *before* starting: with a persistent jobstore, starting
    first lets the background thread process previously-persisted (misfired) jobs
    while ``replace_existing=True`` re-registration removes/re-adds the same ids,
    which surfaces as ``JobLookupError`` on ``update_job``.
    """
    global _scheduler
    if _scheduler is None:
        raise RuntimeError("Scheduler not initialized. Call init_scheduler first.")
    _scheduler.start()
    logger.info("Scheduler started | jobstore=sqlalchemy timezone=UTC | pending_jobs=%d", len(_scheduler.get_jobs()))


def _ensure_failed_jobs_table() -> None:
    """Create the ``failed_cron_jobs`` table if it doesn't exist yet."""
    from app.cron.cron_model import FailedCronJob
    from app.db.base import Base

    try:
        FailedCronJob.__table__.create(engine, checkfirst=True)
        logger.info("Ensured table exists: failed_cron_jobs")
    except Exception as exc:
        logger.warning("Could not ensure failed_cron_jobs table: %s", exc)


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler:
        jobs = _scheduler.get_jobs()
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler shut down | pending_jobs=%d", len(jobs))
        _scheduler = None

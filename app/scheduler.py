from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings

_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        raise RuntimeError("Scheduler not initialized. Call init_scheduler first.")
    return _scheduler


def init_scheduler() -> BackgroundScheduler:
    global _scheduler
    jobstore = SQLAlchemyJobStore(url=settings.DATABASE_URL)
    _scheduler = BackgroundScheduler(
        jobstores={"default": jobstore},
        timezone="UTC",
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 1800,
        },
    )
    _scheduler.start()
    return _scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None

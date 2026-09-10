"""Daily sweep: Super Admin in-app notice when an org has had no login for 30+ days.

Skips deleted and suspended tenants. Does not send email and does not change
tenant status. Dedupe keys keep a daily run from creating duplicate rows.
"""

from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.cron.retry import with_cron_retry
from app.core.logger import get_logger
from app.db.session import SessionLocal
from app.modules.tenants.tenant_service import TenantService

logger = get_logger(__name__)

JOB_ID = "org_inactivity"
JOB_NAME = "Org Inactivity"
JOB_DESCRIPTION = (
    "Notifies Super Admins in-app when an active organization has had no login for 30+ days"
)


def _run_org_inactivity_job() -> None:
    started = datetime.now(timezone.utc)

    def _execute() -> None:
        db = SessionLocal()
        try:
            count = TenantService(db).notify_inactive_organizations()
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
            if count > 0:
                logger.info(
                    "[%s] completed | count=%s elapsed_seconds=%.2f",
                    JOB_NAME,
                    count,
                    elapsed,
                )
        finally:
            db.close()

    with_cron_retry(
        job_id=JOB_ID,
        fn=_execute,
        max_attempts=3,
        job_name=JOB_NAME,
        trigger="cron",
    )


def setup_org_inactivity_jobs(scheduler: BackgroundScheduler) -> None:
    scheduler.add_job(
        _run_org_inactivity_job,
        trigger=CronTrigger(hour=6, minute=0),
        id=JOB_ID,
        replace_existing=True,
        name=JOB_NAME,
    )
    job = scheduler.get_job(JOB_ID)
    logger.info(
        "Registered cron job | id=%s name=\"%s\" next_run=%s trigger=%s description=\"%s\"",
        JOB_ID,
        JOB_NAME,
        getattr(job, "next_run_time", None) if job else None,
        job.trigger if job else None,
        JOB_DESCRIPTION,
    )

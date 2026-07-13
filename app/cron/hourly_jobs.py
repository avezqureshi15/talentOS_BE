from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.logger import get_logger
from app.db.session import SessionLocal
from app.modules.forms.form_service import FormService

logger = get_logger(__name__)


def _with_db_logging(name: str, fn):
    def wrapper() -> None:
        db = SessionLocal()
        started = datetime.now(timezone.utc)
        logger.info("%s job started", name)
        try:
            count = fn(db)
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
            logger.info("%s job completed | count=%d elapsed_seconds=%.2f", name, count, elapsed)
        except Exception as exc:
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
            logger.error("%s job failed after %.2fs | %s", name, elapsed, exc)
        finally:
            db.close()
    return wrapper


_run_reminder_job = _with_db_logging("reminder", lambda db: FormService(db).run_reminder_job())
_run_escalation_job = _with_db_logging("escalation", lambda db: FormService(db).run_escalation_job())
_run_expiry_job = _with_db_logging("expiry", lambda db: FormService(db).run_expiry_reconciliation_job())


def setup_form_jobs(scheduler: BackgroundScheduler) -> None:
    scheduler.add_job(
        _run_reminder_job,
        trigger=CronTrigger(hour="*", minute=0),
        id="form_reminder",
        replace_existing=True,
    )
    scheduler.add_job(
        _run_escalation_job,
        trigger=CronTrigger(hour="*", minute=5),
        id="form_escalation",
        replace_existing=True,
    )
    scheduler.add_job(
        _run_expiry_job,
        trigger=CronTrigger(hour="*", minute=10),
        id="form_expiry",
        replace_existing=True,
    )
    logger.info("Form cron jobs registered: reminder @ :00, escalation @ :05, expiry @ :10")

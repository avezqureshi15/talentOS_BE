from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.logger import get_logger
from app.db.session import SessionLocal
from app.modules.forms.form_service import FormService

logger = get_logger(__name__)


def _run_reminder_job() -> None:
    db = SessionLocal()
    started = datetime.now(timezone.utc)
    logger.info("reminder job started")
    try:
        count = FormService(db).run_reminder_job()
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        logger.info("reminder job completed | count=%d elapsed_seconds=%.2f", count, elapsed)
    except Exception as exc:
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        logger.error("reminder job failed after %.2fs | %s", elapsed, exc)
    finally:
        db.close()


def _run_escalation_job() -> None:
    db = SessionLocal()
    started = datetime.now(timezone.utc)
    logger.info("escalation job started")
    try:
        count = FormService(db).run_escalation_job()
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        logger.info("escalation job completed | count=%d elapsed_seconds=%.2f", count, elapsed)
    except Exception as exc:
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        logger.error("escalation job failed after %.2fs | %s", elapsed, exc)
    finally:
        db.close()


def _run_expiry_job() -> None:
    db = SessionLocal()
    started = datetime.now(timezone.utc)
    logger.info("expiry job started")
    try:
        count = FormService(db).run_expiry_reconciliation_job()
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        logger.info("expiry job completed | count=%d elapsed_seconds=%.2f", count, elapsed)
    except Exception as exc:
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        logger.error("expiry job failed after %.2fs | %s", elapsed, exc)
    finally:
        db.close()


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

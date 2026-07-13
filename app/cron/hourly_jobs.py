from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.logger import get_logger
from app.db.session import SessionLocal
from app.modules.forms.form_service import FormService

logger = get_logger(__name__)


def _run_reminder_job() -> None:
    db = SessionLocal()
    try:
        count = FormService(db).run_reminder_job()
        logger.info("Reminder job done: count=%d", count)
    except Exception as exc:
        logger.error("Reminder job failed: %s", exc)
    finally:
        db.close()


def _run_escalation_job() -> None:
    db = SessionLocal()
    try:
        count = FormService(db).run_escalation_job()
        logger.info("Escalation job done: count=%d", count)
    except Exception as exc:
        logger.error("Escalation job failed: %s", exc)
    finally:
        db.close()


def _run_expiry_job() -> None:
    db = SessionLocal()
    try:
        count = FormService(db).run_expiry_reconciliation_job()
        logger.info("Expiry reconciliation job done: count=%d", count)
    except Exception as exc:
        logger.error("Expiry reconciliation job failed: %s", exc)
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

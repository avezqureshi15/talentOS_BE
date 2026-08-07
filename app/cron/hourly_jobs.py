from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.common.exceptions.cron_exception import CronTransientError
from app.core.config import settings
from app.core.logger import get_logger
from app.cron.retry import with_cron_retry
from app.db.session import SessionLocal
from app.modules.forms.form_service import FormService

logger = get_logger(__name__)

JOB_DESCRIPTIONS: dict[str, str] = {
    "form_reminder": "Sends follow-up emails to interviewers who haven't submitted their review forms",
    "form_escalation": "Escalates overdue review forms to the next level (manager or alternate)",
    "form_expiry": "Marks review/slot forms that have exceeded the expiry window as expired",
}
JOB_NAMES: dict[str, str] = {
    "form_reminder": "Form Reminder",
    "form_escalation": "Form Escalation",
    "form_expiry": "Form Expiry",
}


def _log_job_boundary(job_id: str, phase: str, extra: str = "") -> None:
    name = JOB_NAMES.get(job_id, job_id)
    desc = JOB_DESCRIPTIONS.get(job_id, "")
    desc_part = f" — {desc}" if desc else ""
    extra_part = f" | {extra}" if extra else ""
    logger.info("[%s] %s%s%s", name, phase, desc_part, extra_part)


def _run_job_with_retry(job_id: str, job_fn, trigger: str = "cron") -> None:
    started = datetime.now(timezone.utc)

    def _execute() -> None:
        db = SessionLocal()
        try:
            count = job_fn(db)
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
            if count > 0:
                _log_job_boundary(job_id, "completed", f"count={count} elapsed_seconds={elapsed:.2f}")
        finally:
            db.close()

    with_cron_retry(
        job_id=job_id,
        fn=_execute,
        max_attempts=3,
        job_name=JOB_NAMES.get(job_id),
        trigger=trigger,
    )


def _run_reminder_job() -> None:
    _run_job_with_retry("form_reminder", lambda db: FormService(db).run_reminder_job())


def _run_escalation_job() -> None:
    _run_job_with_retry("form_escalation", lambda db: FormService(db).run_escalation_job())


def _run_expiry_job() -> None:
    _run_job_with_retry("form_expiry", lambda db: FormService(db).run_expiry_reconciliation_job())


def _cron_trigger(job_id: str) -> IntervalTrigger | CronTrigger:
    if settings.APP_ENV in ("development", "uat", "staging"):
        return IntervalTrigger(seconds=3)
    triggers = {
        "form_reminder": CronTrigger(hour="*", minute=0),
        "form_escalation": CronTrigger(hour="*", minute=5),
        "form_expiry": CronTrigger(hour="*", minute=10),
    }
    return triggers.get(job_id, CronTrigger(hour="*", minute=0))


def setup_form_jobs(scheduler: BackgroundScheduler) -> None:
    for job_id in ("form_reminder", "form_escalation", "form_expiry"):
        funcs = {
            "form_reminder": _run_reminder_job,
            "form_escalation": _run_escalation_job,
            "form_expiry": _run_expiry_job,
        }
        scheduler.add_job(
            funcs[job_id],
            trigger=_cron_trigger(job_id),
            id=job_id,
            replace_existing=True,
            name=JOB_NAMES[job_id],
        )
    for j in scheduler.get_jobs():
        logger.info("Registered cron job | id=%s name=\"%s\" next_run=%s trigger=%s description=\"%s\"",
                     j.id, j.name, getattr(j, "next_run_time", None), j.trigger, JOB_DESCRIPTIONS.get(j.id, ""))

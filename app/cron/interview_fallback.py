from datetime import datetime, timedelta, timezone

from apscheduler.jobstores.base import JobLookupError
from apscheduler.triggers.date import DateTrigger

from app.core.config import settings
from app.core.logger import get_logger
from app.db.session import SessionLocal
from app.modules.interviews.review_questions_service import ReviewQuestionsService
from app.scheduler import get_scheduler

logger = get_logger(__name__)


def fallback_job_id(interview_id: str) -> str:
    return f"interview_fallback_{interview_id}"


def _fallback_run_date(end_at: datetime) -> datetime:
    run_date = end_at + timedelta(seconds=settings.INTERVIEW_FALLBACK_SECONDS)
    if run_date.tzinfo is None:
        run_date = run_date.replace(tzinfo=timezone.utc)
    return run_date


def schedule_interview_fallback(interview_id: str, end_at: datetime) -> None:
    """Schedule finalize_for_review at end_at + INTERVIEW_FALLBACK_SECONDS."""
    job_id = fallback_job_id(interview_id)
    run_date = _fallback_run_date(end_at)
    try:
        get_scheduler().add_job(
            "app.cron.interview_fallback:run_interview_fallback",
            trigger=DateTrigger(run_date=run_date),
            args=[interview_id],
            id=job_id,
            replace_existing=True,
            misfire_grace_time=1800,
        )
        logger.info(
            "Interview fallback job scheduled | job_id=%s run_date=%s",
            job_id,
            run_date,
        )
    except Exception:
        logger.exception("Failed to schedule interview fallback job | interview_id=%s", interview_id)


def reschedule_interview_fallback(interview_id: str, end_at: datetime) -> None:
    job_id = fallback_job_id(interview_id)
    run_date = _fallback_run_date(end_at)
    try:
        scheduler = get_scheduler()
        if scheduler.get_job(job_id) is None:
            schedule_interview_fallback(interview_id, end_at)
            return
        scheduler.reschedule_job(job_id, trigger=DateTrigger(run_date=run_date))
        logger.info("Interview fallback job rescheduled | job_id=%s run_date=%s", job_id, run_date)
    except Exception as exc:
        logger.warning(
            "Failed to reschedule interview fallback job | job_id=%s | %s",
            job_id,
            exc,
        )


def remove_interview_fallback(interview_id: str) -> None:
    """Remove fallback job (cancel / reschedule paths only — not the webhook)."""
    job_id = fallback_job_id(interview_id)
    try:
        scheduler = get_scheduler()
        if scheduler.get_job(job_id) is None:
            logger.debug("No interview fallback job to remove | interview_id=%s", interview_id)
            return
        scheduler.remove_job(job_id)
        logger.info("Interview fallback job removed | job_id=%s", job_id)
    except JobLookupError:
        logger.debug("No interview fallback job to remove | interview_id=%s", interview_id)
    except Exception:
        logger.exception("Failed to remove interview fallback job | interview_id=%s", interview_id)


def run_interview_fallback(interview_id: str) -> None:
    started = datetime.now(timezone.utc)
    logger.info("Interview fallback job started | interview_id=%s", interview_id)
    db = SessionLocal()
    try:
        # transcription=None → finalize is a full no-op if already COMPLETED.
        ReviewQuestionsService(db).finalize_for_review(
            interview_id,
            transcription=None,
            send_forms=True,
        )
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        logger.info(
            "Interview fallback job finished | interview_id=%s elapsed_seconds=%.2f",
            interview_id,
            elapsed,
        )
    except Exception:
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        logger.exception(
            "Interview fallback job failed after %.2fs | interview_id=%s",
            elapsed,
            interview_id,
        )
        raise
    finally:
        db.close()

"""Reusable retry logic for APScheduler cron jobs.

Usage:
    from app.cron.retry import with_cron_retry

    with_cron_retry(job_id="form_reminder", fn=lambda: do_work())
"""
import time
from datetime import datetime, timezone
from typing import Callable

from app.common.exceptions.cron_exception import CronTransientError
from app.core.logger import get_logger
from app.db.session import SessionLocal
from app.cron.cron_model import FailedCronJob

logger = get_logger(__name__)


def with_cron_retry(
    job_id: str,
    fn: Callable[[], None],
    max_attempts: int = 3,
    is_transient: Callable[[Exception], bool] | None = None,
    job_name: str | None = None,
    trigger: str | None = None,
    payload: str | None = None,
) -> None:
    """Execute ``fn`` with exponential-backoff retry for transient errors.

    If all attempts fail, the failure is persisted to ``failed_cron_jobs``.
    """
    if is_transient is None:
        is_transient = lambda e: isinstance(e, CronTransientError)

    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            fn()
            return
        except Exception as exc:
            last_error = exc
            if is_transient(exc) and attempt < max_attempts:
                delay = min(2 ** attempt, 30)
                logger.warning(
                    "[%s] Transient error (attempt %d/%d) — retrying in %ds: %s",
                    job_id, attempt, max_attempts, delay, exc,
                )
                time.sleep(delay)
            else:
                logger.error(
                    "[%s] Non-retryable error or attempts exhausted (attempt %d/%d): %s",
                    job_id, attempt, max_attempts, exc,
                )
                break

    db = SessionLocal()
    try:
        failed = FailedCronJob(
            job_id=job_id,
            job_name=job_name,
            trigger=trigger,
            error_reason=str(last_error)[:2000] if last_error else "Unknown error",
            payload=payload,
            attempts=0,
        )
        db.add(failed)
        db.commit()
        logger.info("[%s] Failure recorded in failed_cron_jobs | id=%s", job_id, failed.id)
    except Exception as exc2:
        logger.error("[%s] Failed to persist failed job record: %s", job_id, exc2)
        db.rollback()
    finally:
        db.close()

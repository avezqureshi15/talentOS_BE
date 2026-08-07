"""Periodic sweep that detects AI screening outcomes that never reach us via push.

The POC only pushes successful (transcript-bearing) screening results. Failed
calls (no_answer/voicemail/dropped/declined/failed) stay terminal on the POC
side only, so this job pulls the latest screening *status* (pending /
completed / flagged) for candidates still in the screening pipeline:

  - flagged (never-completable) -> candidate moves to AI_SCREENING_FLAGGED and
    a flag review + notification is recorded (apply_screening_flag)
  - completed (real result)    -> candidate advances to UNDER_EVALUATION
  - pending (retries possible) -> candidate stays put (SCREENING_ROUND_SCHEDULED)
    but the latest call_status / retry_count are refreshed so live states
    (in progress, retry scheduled) reach the frontend

If the POC doesn't yet expose the screening-status endpoint, the sweep falls
back to the legacy get_screening_result + apply_screening_outcome path so the
old behaviour is preserved during rolling deployments.

Pull failures are skipped (a later run picks them up); the sweep itself is
retried via with_cron_retry and recorded in failed_cron_jobs when it can't run.
"""

import asyncio
from datetime import datetime, timezone
from uuid import UUID

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.core.ai_recruitment_client import AiRecruitmentClient
from app.core.config import settings
from app.core.logger import get_logger
from app.cron.retry import with_cron_retry
from app.db.session import SessionLocal
from app.modules.talentos_integration.talentos_result_service import (
    apply_screening_flag,
    apply_screening_outcome,
    update_screening_call_status,
)

logger = get_logger(__name__)

JOB_ID = "screening_outcome_sweep"
JOB_NAME = "AI Screening Outcome Sweep"

_SCREENING_STATUSES = ("SCREENING_ROUND_SCHEDULED", "AI_SCREENING_EVALUATION_FAILED")


def _cron_trigger() -> IntervalTrigger | CronTrigger:
    if settings.APP_ENV in ("development", "uat", "staging"):
        return IntervalTrigger(seconds=3)
    return IntervalTrigger(minutes=5)


async def _apply_legacy_result(db, candidate, round_id, client, external_job_id) -> bool:
    """Legacy fallback: pull get_screening_result and apply the outcome."""
    try:
        result = await client.get_screening_result(
            external_job_id, candidate.rh_external_candidate_id
        )
    except Exception as exc:
        logger.warning(
            "screening outcome sweep: pull failed | candidate_id=%s err=%s",
            candidate.id, exc,
        )
        return False
    if not isinstance(result, dict) or not result:
        return False
    apply_screening_outcome(db, round_id, candidate, result)
    return True


async def _sweep_once(db) -> int:
    from app.modules.evaluations.evaluation_model import Candidate
    from app.modules.hiring_requests.hiring_request_model import HiringRequest

    candidates = (
        db.query(Candidate)
        .filter(
            Candidate.stage == "AI_SCREENING",
            Candidate.status.in_(_SCREENING_STATUSES),
        )
        .all()
    )
    if not candidates:
        return 0

    client = AiRecruitmentClient()
    processed = 0
    for candidate in candidates:
        if not candidate.current_round_id or not candidate.rh_external_candidate_id:
            continue
        try:
            external = UUID(str(candidate.external_job_id))
        except (ValueError, TypeError):
            continue
        hr = (
            db.query(HiringRequest)
            .filter(
                (HiringRequest.id == external)
                | (HiringRequest.external_job_id == external)
            )
            .first()
        )
        if hr is None or not hr.rh_external_job_id:
            continue
        try:
            status = await client.get_screening_status(
                str(hr.rh_external_job_id), candidate.rh_external_candidate_id
            )
        except Exception as exc:
            logger.warning(
                "screening outcome sweep: status pull failed | candidate_id=%s err=%s",
                candidate.id, exc,
            )
            continue

        if not isinstance(status, dict) or not status:
            if await _apply_legacy_result(
                db, candidate, candidate.current_round_id, client, str(hr.rh_external_job_id)
            ):
                processed += 1
            continue

        disposition = status.get("disposition")
        if disposition == "flagged":
            apply_screening_flag(db, candidate.current_round_id, candidate, status)
            processed += 1
        elif disposition == "completed":
            result = status.get("latest_call")
            if isinstance(result, dict) and result:
                apply_screening_outcome(db, candidate.current_round_id, candidate, result)
                processed += 1
        else:
            # disposition == "pending": the POC may still be dialing, have a
            # call in progress, or have a retry scheduled — keep the candidate
            # in place but refresh the live call status so the frontend shows
            # the current state (in_progress / retry scheduled) instead of a
            # stale "queued".
            latest = status.get("latest_call")
            if isinstance(latest, dict) and latest.get("call_status"):
                changed = update_screening_call_status(
                    db,
                    candidate.current_round_id,
                    str(latest.get("call_status")),
                    latest.get("retry_count"),
                )
                if changed:
                    processed += 1
    return processed


def _run_sweep() -> None:
    started = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        count = asyncio.run(_sweep_once(db))
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        logger.info(
            "screening_outcome_sweep completed | count=%d elapsed_seconds=%.2f",
            count, elapsed,
        )
    finally:
        db.close()


def _run_sweep_with_retry() -> None:
    with_cron_retry(
        job_id=JOB_ID,
        fn=_run_sweep,
        max_attempts=3,
        job_name=JOB_NAME,
        trigger="interval",
    )


def setup_screening_jobs(scheduler: BackgroundScheduler) -> None:
    scheduler.add_job(
        _run_sweep_with_retry,
        trigger=_cron_trigger(),
        id=JOB_ID,
        replace_existing=True,
        name=JOB_NAME,
    )
    job = scheduler.get_job(JOB_ID)
    if job:
        logger.info(
            "Registered cron job | id=%s name=\"%s\" next_run=%s trigger=%s",
            job.id, job.name, getattr(job, "next_run_time", None), job.trigger,
        )

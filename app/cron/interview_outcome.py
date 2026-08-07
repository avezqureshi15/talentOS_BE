"""Periodic sweep that pulls AI interview results when the POC push misses.

The POC pushes interview completions via ``/internal/talentos/webhooks/interview``,
but a failed/never-arrived push (talentOS briefly down, transport error, POC
crash) would otherwise strand candidates in ``INTERVIEW_SCHEDULED`` forever.
This job polls candidates still in the AI_INTERVIEW stage and pulls + persists
any interview session that has reached a terminal status, applying the same
status mapping as the webhook push (full sync):

  - in_progress -> ONGOING
  - assessed/completed -> UNDER_EVALUATION (report transform enqueued)
  - expired / never-started -> NO_SHOW (with a flag reason)
  - pending/active -> candidate stays put (nothing to pull yet)

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
    _is_interview_failure,
    _default_flag_reason,
    _map_result_to_status,
    apply_interview_status_update,
    persist_interview_result,
)

logger = get_logger(__name__)

JOB_ID = "interview_outcome_sweep"
JOB_NAME = "AI Interview Outcome Sweep"

_ACTIVE_STATUSES = ("INTERVIEW_SCHEDULED", "INTERVIEW_RESCHEDULED", "ONGOING")
_NON_TERMINAL_STATUSES = {"pending", "active"}


def _cron_trigger() -> IntervalTrigger | CronTrigger:
    if settings.APP_ENV in ("development", "uat", "staging"):
        return IntervalTrigger(seconds=5)
    return IntervalTrigger(minutes=5)


async def _sweep_once(db) -> int:
    from app.modules.evaluations.evaluation_model import Candidate
    from app.modules.hiring_requests.hiring_request_model import HiringRequest
    from app.modules.rounds.round_model import Round

    candidates = (
        db.query(Candidate)
        .filter(
            Candidate.stage == "AI_INTERVIEW",
            Candidate.status.in_(_ACTIVE_STATUSES),
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
            interviews = await client.list_interviews(
                str(hr.rh_external_job_id), candidate.rh_external_candidate_id
            )
        except Exception as exc:
            logger.warning(
                "interview outcome sweep: list failed | candidate_id=%s err=%s",
                candidate.id, exc,
            )
            continue
        if not isinstance(interviews, list) or not interviews:
            continue

        latest = interviews[0]
        if not isinstance(latest, dict) or not latest.get("id"):
            continue
        status = (latest.get("status") or "").lower()
        if status in _NON_TERMINAL_STATUSES:
            continue

        interview_id = str(latest.get("id"))
        try:
            detail = await client.get_interview_detail(
                str(hr.rh_external_job_id),
                candidate.rh_external_candidate_id,
                interview_id,
            )
        except Exception as exc:
            logger.warning(
                "interview outcome sweep: detail pull failed | candidate_id=%s "
                "interview_id=%s err=%s",
                candidate.id, interview_id, exc,
            )
            continue
        if not isinstance(detail, dict) or not detail:
            continue

        round_obj = (
            db.query(Round).filter(Round.id == candidate.current_round_id).first()
        )
        if round_obj is None:
            continue
        if not round_obj.rh_external_session_id:
            round_obj.rh_external_session_id = interview_id
            db.commit()

        mapped_status = _map_result_to_status(detail)
        if mapped_status is None:
            continue

        flag_reason = detail.get("flag_reason") or _default_flag_reason(
            (detail.get("status") or "").lower()
        )
        apply_interview_status_update(
            db, round_obj.id, candidate, mapped_status, flag_reason
        )
        if mapped_status in (
            "UNDER_EVALUATION",
            "INTERVIEW_SCHEDULED",
            "ONGOING",
        ):
            persist_interview_result(
                db,
                round_obj,
                detail,
                enqueue_report=(mapped_status == "UNDER_EVALUATION"),
            )

        if _is_interview_failure(detail) and round_obj.jd_id:
            from app.modules.talentos_integration.talentos_result_service import (
                _notify_ai_failure,
            )

            _notify_ai_failure(
                db,
                hiring_request_id=round_obj.jd_id,
                round_id=round_obj.id,
                candidate_id=candidate.id,
                entity_type="ai_interview",
                round_name=round_obj.name,
                title="AI interview assessment failed",
                body=(
                    f"AI interview round \"{round_obj.name or round_obj.id}\" could not be "
                    f"assessed (status: {detail.get('status') or 'unknown'}). "
                    "You can retry the assessment from the AI interview view."
                ),
            )
        processed += 1
    return processed


def _run_sweep() -> None:
    started = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        count = asyncio.run(_sweep_once(db))
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        logger.info(
            "interview_outcome_sweep completed | count=%d elapsed_seconds=%.2f",
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


def setup_interview_jobs(scheduler: BackgroundScheduler) -> None:
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
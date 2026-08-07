import uuid
from datetime import datetime, timezone

from apscheduler.jobstores.base import JobLookupError
from apscheduler.triggers.date import DateTrigger

from app.core.constants import EvaluationStatus, PipelineStage
from app.core.logger import get_logger
from app.cron.retry import with_cron_retry
from app.db.session import SessionLocal
from app.modules.events.event_schema import EventCreate
from app.modules.events.event_service import EventService
from app.scheduler import get_scheduler

logger = get_logger(__name__)

_ACTIVE_STATUSES = (
    EvaluationStatus.INTERVIEW_SCHEDULED.value,
    EvaluationStatus.INTERVIEW_RESCHEDULED.value,
    EvaluationStatus.ONGOING.value,
)


def ongoing_job_id(interview_id: str) -> str:
    return f"interview_ongoing_{interview_id}"


def _ongoing_run_date(start_at: datetime) -> datetime:
    run_date = start_at
    if run_date.tzinfo is None:
        run_date = run_date.replace(tzinfo=timezone.utc)
    return run_date


def schedule_interview_ongoing(interview_id: str, start_at: datetime) -> None:
    """Schedule marking the candidate as ONGOING at the interview start time."""
    job_id = ongoing_job_id(interview_id)
    run_date = _ongoing_run_date(start_at)
    try:
        get_scheduler().add_job(
            "app.cron.interview_ongoing:run_interview_ongoing",
            trigger=DateTrigger(run_date=run_date),
            args=[interview_id],
            id=job_id,
            replace_existing=True,
            misfire_grace_time=1800,
        )
        logger.info(
            "Interview ongoing job scheduled | job_id=%s run_date=%s",
            job_id,
            run_date,
        )
    except Exception:
        logger.exception("Failed to schedule interview ongoing job | interview_id=%s", interview_id)


def reschedule_interview_ongoing(interview_id: str, start_at: datetime) -> None:
    job_id = ongoing_job_id(interview_id)
    run_date = _ongoing_run_date(start_at)
    try:
        scheduler = get_scheduler()
        if scheduler.get_job(job_id) is None:
            schedule_interview_ongoing(interview_id, start_at)
            return
        scheduler.reschedule_job(job_id, trigger=DateTrigger(run_date=run_date))
        logger.info("Interview ongoing job rescheduled | job_id=%s run_date=%s", job_id, run_date)
    except Exception as exc:
        logger.warning(
            "Failed to reschedule interview ongoing job | job_id=%s | %s",
            job_id,
            exc,
        )


def remove_interview_ongoing(interview_id: str) -> None:
    """Remove the ongoing job (cancel path only — not the webhook)."""
    job_id = ongoing_job_id(interview_id)
    try:
        scheduler = get_scheduler()
        if scheduler.get_job(job_id) is None:
            logger.debug("No interview ongoing job to remove | interview_id=%s", interview_id)
            return
        scheduler.remove_job(job_id)
        logger.info("Interview ongoing job removed | job_id=%s", job_id)
    except JobLookupError:
        logger.debug("No interview ongoing job to remove | interview_id=%s", interview_id)
    except Exception:
        logger.exception("Failed to remove interview ongoing job | interview_id=%s", interview_id)


def _do_mark_ongoing(interview_id: str) -> None:
    started = datetime.now(timezone.utc)
    logger.info("Interview ongoing job started | interview_id=%s", interview_id)
    db = SessionLocal()
    try:
        from app.modules.evaluations.evaluation_model import Candidate
        from app.modules.interviews.models.interview import Interview
        from app.modules.rounds.round_model import Round

        interview = db.query(Interview).filter(Interview.id == uuid.UUID(interview_id)).first()
        if not interview:
            logger.info("Interview not found | interview_id=%s", interview_id)
            return

        round_obj = db.query(Round).filter(Round.id == interview.round_id).first()
        candidate_id = round_obj.candidate_id if round_obj else None
        if not candidate_id:
            logger.info("Round/candidate not found | interview_id=%s", interview_id)
            return

        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not candidate:
            logger.info("Candidate not found | candidate_id=%s", candidate_id)
            return

        if candidate.stage != PipelineStage.INTERVIEW.value:
            logger.info(
                "Ongoing skipped | not a regular human interview | candidate_id=%s stage=%s",
                candidate_id, candidate.stage,
            )
            return

        if candidate.status not in _ACTIVE_STATUSES:
            logger.info(
                "Ongoing skipped | candidate not in scheduled state | candidate_id=%s status=%s",
                candidate_id, candidate.status,
            )
            return

        previous_stage = candidate.stage
        candidate.status = EvaluationStatus.ONGOING.value
        candidate.stage = PipelineStage.INTERVIEW.value
        db.commit()

        EventService(db).create_event(EventCreate(
            entity_type="CANDIDATE",
            entity_id=str(candidate_id),
            candidate_id=candidate_id,
            event_name="Interview Ongoing",
            state_code=EvaluationStatus.ONGOING.value,
            actor_type="SYSTEM",
            event_metadata={"interview_id": interview_id, "round_id": str(interview.round_id), "previous_stage": previous_stage},
        ))

        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        logger.info(
            "Interview marked ongoing | candidate_id=%s interview_id=%s new_status=%s elapsed_seconds=%.2f",
            candidate_id, interview_id, EvaluationStatus.ONGOING.value, elapsed,
        )
    except Exception:
        db.rollback()
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        logger.error("Interview ongoing job failed after %.2fs | interview_id=%s", elapsed, interview_id)
        raise
    finally:
        db.close()


def run_interview_ongoing(interview_id: str) -> None:
    with_cron_retry(
        job_id=ongoing_job_id(interview_id),
        fn=lambda: _do_mark_ongoing(interview_id),
        max_attempts=3,
        job_name="Interview Ongoing",
        trigger="date",
        payload=interview_id,
    )

from datetime import datetime, timezone

from app.core.constants import EvaluationStatus
from app.core.logger import get_logger
from app.cron.retry import with_cron_retry
from app.db.session import SessionLocal
from app.modules.events.event_schema import EventCreate
from app.modules.events.event_service import EventService

logger = get_logger(__name__)


def _do_complete_ai_round(candidate_id: int, round_id: str) -> None:
    started = datetime.now(timezone.utc)
    logger.info("AI round completion job started | candidate_id=%s round_id=%s", candidate_id, round_id)
    db = SessionLocal()
    try:
        from app.modules.evaluations.evaluation_model import Candidate
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not candidate:
            logger.info("Candidate not found | candidate_id=%s", candidate_id)
            return

        if candidate.status not in ("INTERVIEW_SCHEDULED", "SCREENING_ROUND_SCHEDULED"):
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
            logger.info(
                "AI round already past scheduled state | candidate_id=%s status=%s elapsed_seconds=%.2f",
                candidate_id, candidate.status, elapsed,
            )
            return

        previous_stage = candidate.stage
        candidate.stage = f"{candidate.stage}_EVALUATED"
        candidate.status = EvaluationStatus.UNDER_EVALUATION.value
        db.commit()

        EventService(db).create_event(EventCreate(
            entity_type="CANDIDATE",
            entity_id=str(candidate_id),
            candidate_id=candidate_id,
            event_name="AI Round Completed",
            state_code=EvaluationStatus.UNDER_EVALUATION.value,
            actor_type="SYSTEM",
            event_metadata={"round_id": round_id, "previous_stage": previous_stage},
        ))

        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        logger.info(
            "AI round completed | candidate_id=%s round_id=%s new_status=%s elapsed_seconds=%.2f",
            candidate_id, round_id, EvaluationStatus.UNDER_EVALUATION.value, elapsed,
        )
    except Exception:
        db.rollback()
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        logger.error("AI round completion failed after %.2fs | candidate_id=%s round_id=%s", elapsed, candidate_id, round_id)
        raise
    finally:
        db.close()


def complete_ai_round(candidate_id: int, round_id: str) -> None:
    with_cron_retry(
        job_id=f"ai_round_complete_{round_id}",
        fn=lambda: _do_complete_ai_round(candidate_id, round_id),
        max_attempts=3,
        job_name="AI Round Completion",
        trigger="date",
        payload=round_id,
    )

import uuid
from datetime import datetime, timezone

from app.core.constants import EvaluationStatus, InterviewStatus
from app.core.logger import get_logger
from app.db.session import SessionLocal
from app.modules.events.event_schema import EventCreate
from app.modules.events.event_service import EventService
from app.modules.interviews.models.interview import Interview
from app.modules.rounds.round_model import Round
from app.modules.evaluations.evaluation_model import Candidate

logger = get_logger(__name__)


def complete_interview(interview_id: str) -> None:
    started = datetime.now(timezone.utc)
    logger.info("Interview completion job started | interview_id=%s", interview_id)
    db = SessionLocal()
    try:
        interview = db.query(Interview).filter(
            Interview.id == uuid.UUID(interview_id),
            Interview.status.in_([InterviewStatus.SCHEDULED.value, InterviewStatus.RESCHEDULED.value]),
        ).first()
        if not interview:
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
            logger.info("Interview not found or already completed | interview_id=%s elapsed_seconds=%.2f", interview_id, elapsed)
            return

        round_ = db.query(Round).filter(Round.id == interview.round_id).first()
        candidate_id = round_.candidate_id if round_ else None

        interview.status = InterviewStatus.COMPLETED.value

        if candidate_id:
            db.query(Candidate).filter(Candidate.id == candidate_id).update(
                {"status": EvaluationStatus.INTERVIEW_COMPLETED.value}
            )
            EventService(db).create_event(EventCreate(
                entity_type="CANDIDATE",
                entity_id=str(candidate_id),
                event_name="Interview Completed",
                state_code=EvaluationStatus.INTERVIEW_COMPLETED.value,
                actor_type="SYSTEM",
                candidate_id=candidate_id,
                event_metadata={"interview_id": interview_id, "round_id": str(interview.round_id), "round_name": round_.name if round_ else None},
            ))

        db.commit()
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        logger.info("Interview completed | interview_id=%s candidate_id=%s round_id=%s elapsed_seconds=%.2f", interview_id, candidate_id, interview.round_id, elapsed)
    except Exception:
        db.rollback()
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        logger.error("Interview completion failed after %.2fs | interview_id=%s", elapsed, interview_id)
        raise
    finally:
        db.close()

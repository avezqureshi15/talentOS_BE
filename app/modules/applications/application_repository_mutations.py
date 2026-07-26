from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.constants import EvaluationStatus
from app.core.logger import get_logger
from app.modules.evaluations.evaluation_model import Candidate

logger = get_logger(__name__)


def create_queued_candidate(db: Session, application_id: str, job_id: str, **kwargs) -> Candidate:
    candidate = Candidate(
        external_application_id=application_id,
        external_job_id=job_id,
        candidate_name=kwargs.get("candidate_name"),
        candidate_email=kwargs.get("candidate_email"),
        candidate_phone=kwargs.get("candidate_phone"),
        cover_letter=kwargs.get("cover_letter"),
        resume_url=kwargs.get("resume_url"),
        current_ctc=kwargs.get("current_ctc"),
        expected_ctc=kwargs.get("expected_ctc"),
        location=kwargs.get("location"),
        years_of_experience=kwargs.get("years_of_experience"),
        notice_period=kwargs.get("notice_period"),
        how_did_you_hear=kwargs.get("how_did_you_hear"),
        linkedin_url=kwargs.get("linkedin_url"),
        willing_to_relocate=kwargs.get("willing_to_relocate", False),
        candidate_type=kwargs.get("candidate_type", "REGULAR"),
        status=EvaluationStatus.QUEUED.value,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    logger.info("Created queued candidate: external_application_id=%s | external_job_id=%s", application_id, job_id)
    return candidate


def mark_processing(db: Session, candidate: Candidate) -> Candidate:
    candidate.status = EvaluationStatus.RESUME_PROCESSING.value
    candidate.attempts += 1
    db.commit()
    db.refresh(candidate)
    return candidate


def mark_result(db: Session, candidate: Candidate, status: EvaluationStatus, fit_score: int | None = None, summary_md: str | None = None, ats_threshold_used: int | None = None, error_reason: str | None = None) -> Candidate:
    candidate.status = status.value
    candidate.fit_score = fit_score
    candidate.summary_md = summary_md
    candidate.ats_threshold_used = ats_threshold_used
    candidate.error_reason = error_reason
    candidate.evaluated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(candidate)
    return candidate


def set_current_round_id(db: Session, candidate: Candidate, round_id: UUID) -> Candidate:
    candidate.current_round_id = round_id
    db.commit()
    db.refresh(candidate)
    logger.info("Set current_round_id: candidate_id=%s | round_id=%s", candidate.id, round_id)
    return candidate


def set_final_verdict(db: Session, candidate_id: int, verdict: str) -> Candidate | None:
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        return None
    candidate.final_verdict = verdict
    db.commit()
    db.refresh(candidate)
    logger.info("Set final_verdict: candidate_id=%s | verdict=%s", candidate_id, verdict)
    return candidate


def update_status(db: Session, candidate_id: int, new_status: str) -> Candidate | None:
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        return None
    if candidate.final_verdict is not None:
        return None
    candidate.status = new_status
    db.flush()
    logger.info("Updated candidate status: candidate_id=%s | status=%s", candidate_id, new_status)
    return candidate


def apply_transition(db: Session, candidate_id: int, final_verdict: str | None = None, status: str | None = None) -> Candidate | None:
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        return None
    if final_verdict is not None:
        candidate.final_verdict = final_verdict
        if status is not None:
            candidate.status = status
    elif status is not None:
        if candidate.final_verdict is not None:
            return None
        candidate.status = status
    else:
        return candidate
    db.commit()
    db.refresh(candidate)
    logger.info("Applied transition: candidate_id=%s | final_verdict=%s | status=%s", candidate_id, final_verdict, status)
    return candidate

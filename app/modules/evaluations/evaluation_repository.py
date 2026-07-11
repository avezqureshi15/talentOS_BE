from uuid import UUID

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.constants import EvaluationStatus
from app.core.logger import get_logger
from app.modules.evaluations.evaluation_model import Candidate

logger = get_logger(__name__)


class EvaluationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_application_id(self, application_id: str) -> Candidate | None:
        return (
            self.db.query(Candidate)
            .filter(Candidate.external_application_id == application_id)
            .first()
        )

    def create_queued(
        self,
        application_id: str,
        job_id: str,
        candidate_name: str | None,
        candidate_email: str | None,
        candidate_phone: str | None = None,
        cover_letter: str | None = None,
        resume_url: str | None = None,
        current_ctc: str | None = None,
        expected_ctc: str | None = None,
        location: str | None = None,
        years_of_experience: str | None = None,
        notice_period: str | None = None,
        how_did_you_hear: str | None = None,
        linkedin_url: str | None = None,
        willing_to_relocate: bool = False,
    ) -> Candidate:
        evaluation = Candidate(
            external_application_id=application_id,
            external_job_id=job_id,
            candidate_name=candidate_name,
            candidate_email=candidate_email,
            candidate_phone=candidate_phone,
            cover_letter=cover_letter,
            resume_url=resume_url,
            current_ctc=current_ctc,
            expected_ctc=expected_ctc,
            location=location,
            years_of_experience=years_of_experience,
            notice_period=notice_period,
            how_did_you_hear=how_did_you_hear,
            linkedin_url=linkedin_url,
            willing_to_relocate=willing_to_relocate,
            status=EvaluationStatus.QUEUED.value,
        )
        self.db.add(evaluation)
        self.db.commit()
        self.db.refresh(evaluation)
        logger.info("Created queued evaluation: external_application_id=%s | external_job_id=%s", application_id, job_id)
        return evaluation

    def mark_processing(self, evaluation: Candidate) -> Candidate:
        evaluation.status = EvaluationStatus.PROCESSING.value
        evaluation.attempts += 1
        self.db.commit()
        self.db.refresh(evaluation)
        logger.info("Marked evaluation processing: id=%s | attempt=%d", evaluation.external_application_id, evaluation.attempts)
        return evaluation

    def set_current_round_id(self, evaluation: Candidate, round_id: UUID) -> Candidate:
        evaluation.current_round_id = round_id
        self.db.commit()
        self.db.refresh(evaluation)
        logger.info("Set current_round_id: candidate_id=%s | round_id=%s", evaluation.id, round_id)
        return evaluation

    def mark_result(
        self,
        evaluation: Candidate,
        status: EvaluationStatus,
        fit_score: int | None = None,
        summary_md: str | None = None,
        ats_threshold_used: int | None = None,
        error_reason: str | None = None,
    ) -> Candidate:
        evaluation.status = status.value
        evaluation.fit_score = fit_score
        evaluation.summary_md = summary_md
        evaluation.ats_threshold_used = ats_threshold_used
        evaluation.error_reason = error_reason
        evaluation.evaluated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(evaluation)
        logger.info(
            "Evaluation result: external_application_id=%s | status=%s | score=%s | error=%s",
            evaluation.external_application_id, status.value, fit_score, error_reason,
        )
        return evaluation

    def get_by_job(self, job_id: str, status: str | None = None) -> list[Candidate]:
        query = self.db.query(Candidate).filter(Candidate.external_job_id == job_id)
        if status:
            query = query.filter(Candidate.status == status)
        return query.order_by(Candidate.fit_score.desc().nullslast()).all()

    def get_by_job_paginated(
        self,
        job_id: str | None = None,
        status: str | None = None,
        schedule: str | None = None,
        min_score: int | None = None,
        max_score: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Candidate], int]:
        query = self.db.query(Candidate)

        if job_id:
            query = query.filter(Candidate.external_job_id == job_id)
        if status:
            query = query.filter(Candidate.status == status)
        if schedule == "scheduled":
            query = query.filter(Candidate.scheduled == True)
        elif schedule == "unscheduled":
            query = query.filter(Candidate.scheduled == False)
        if min_score is not None:
            query = query.filter(Candidate.fit_score >= min_score)
        if max_score is not None:
            query = query.filter(Candidate.fit_score <= max_score)
        if date_from:
            query = query.filter(Candidate.created_at >= date_from)
        if date_to:
            query = query.filter(Candidate.created_at <= date_to)

        total = query.count()
        items = (
            query
            .order_by(Candidate.fit_score.desc().nullslast())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return items, total

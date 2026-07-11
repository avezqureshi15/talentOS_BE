from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.constants import EvaluationStatus
from app.core.logger import get_logger
from app.modules.evaluations.evaluation_model import Candidate
from app.modules.hiring_requests.hiring_request_model import HiringRequest

logger = get_logger(__name__)


class ApplicationRepository:
    def __init__(self, db: Session):
        self.db = db

    # ── hiring request resolution ────────────────────────────────

    def resolve_external_job_id(self, job_id: str) -> str | None:
        """Resolve a hiring_request.id to its external_job_id."""
        try:
            hr_uuid = UUID(job_id)
            hr = self.db.query(HiringRequest).filter(HiringRequest.id == hr_uuid).first()
            if hr and hr.external_job_id:
                return str(hr.external_job_id)
            return None
        except (ValueError, TypeError):
            return None

    # ── candidate lookups ────────────────────────────────────────

    def get_candidate_by_application_id(self, application_id: str) -> Candidate | None:
        return (
            self.db.query(Candidate)
            .filter(Candidate.external_application_id == application_id)
            .first()
        )

    def get_candidates_by_job(
        self, job_id: str, status: str | None = None
    ) -> list[Candidate]:
        query = self.db.query(Candidate).filter(Candidate.external_job_id == job_id)
        if status:
            query = query.filter(Candidate.status == status)
        return query.order_by(Candidate.fit_score.desc().nullslast()).all()

    def get_candidates_by_job_paginated(
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
            query.order_by(Candidate.fit_score.desc().nullslast())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return items, total

    # ── candidate mutations ──────────────────────────────────────

    def create_queued_candidate(
        self,
        application_id: str,
        job_id: str,
        candidate_name: str | None = None,
        candidate_email: str | None = None,
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
        candidate = Candidate(
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
        self.db.add(candidate)
        self.db.commit()
        self.db.refresh(candidate)
        logger.info("Created queued candidate: external_application_id=%s | external_job_id=%s", application_id, job_id)
        return candidate

    def mark_processing(self, candidate: Candidate) -> Candidate:
        candidate.status = EvaluationStatus.PROCESSING.value
        candidate.attempts += 1
        self.db.commit()
        self.db.refresh(candidate)
        return candidate

    def mark_result(
        self,
        candidate: Candidate,
        status: EvaluationStatus,
        fit_score: int | None = None,
        summary_md: str | None = None,
        ats_threshold_used: int | None = None,
        error_reason: str | None = None,
    ) -> Candidate:
        candidate.status = status.value
        candidate.fit_score = fit_score
        candidate.summary_md = summary_md
        candidate.ats_threshold_used = ats_threshold_used
        candidate.error_reason = error_reason
        candidate.evaluated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(candidate)
        return candidate

    # ── response mapping ─────────────────────────────────────────

    @staticmethod
    def to_candidate_dict(candidate: Candidate) -> dict:
        return {
            "id": candidate.external_application_id,
            "job_id": candidate.external_job_id,
            "name": candidate.candidate_name,
            "email": candidate.candidate_email,
            "phone": candidate.candidate_phone,
            "cover_letter": candidate.cover_letter,
            "resume_url": candidate.resume_url,
            "current_ctc": candidate.current_ctc,
            "expected_ctc": candidate.expected_ctc,
            "location": candidate.location,
            "years_of_experience": candidate.years_of_experience,
            "notice_period": candidate.notice_period,
            "how_did_you_hear": candidate.how_did_you_hear,
            "linkedin_url": candidate.linkedin_url,
            "willing_to_relocate": candidate.willing_to_relocate if candidate.willing_to_relocate is not None else False,
            "status": candidate.status,
            "fit_score": candidate.fit_score,
            "summary_md": candidate.summary_md,
            "evaluated_at": candidate.evaluated_at.isoformat() if candidate.evaluated_at else None,
            "scheduled": candidate.scheduled,
        }

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.modules.applications import application_repository_mutations as _mut
from app.modules.applications.application_repository_queries import (
    build_review_map,
    get_candidates_by_job_paginated as _get_candidates_by_job_paginated,
    get_finalized_candidates as _get_finalized_candidates,
)
from app.modules.applications.application_response import build_candidate_response, get_ai_review
from app.modules.evaluations.evaluation_model import Candidate
from app.modules.hiring_requests.hiring_request_model import HiringRequest
from app.modules.reviews.review_model import Review

logger = get_logger(__name__)


class ApplicationRepository:
    def __init__(self, db: Session):
        self.db = db
        self._review_map: dict[str, Review] = {}

    def resolve_external_job_id(self, job_id: str) -> str | None:
        try:
            hr_uuid = UUID(job_id)
            hr = self.db.query(HiringRequest).filter(HiringRequest.id == hr_uuid).first()
            if hr and hr.external_job_id:
                return str(hr.external_job_id)
            return None
        except (ValueError, TypeError):
            return None

    def resolve_hiring_request_id(self, external_job_id: str) -> UUID | None:
        try:
            uuid_val = UUID(external_job_id)
            hr = self.db.query(HiringRequest).filter(HiringRequest.external_job_id == uuid_val).first()
            return hr.id if hr else None
        except (ValueError, TypeError):
            return None

    def get_candidate_by_application_id(self, application_id: str) -> Candidate | None:
        return (
            self.db.query(Candidate)
            .filter(Candidate.external_application_id == application_id)
            .first()
        )

    def get_candidates_by_job(self, job_id: str, status: str | None = None) -> list[Candidate]:
        query = self.db.query(Candidate).filter(Candidate.external_job_id == job_id)
        if status:
            query = query.filter(Candidate.status == status)
        return query.order_by(Candidate.fit_score.desc().nullslast()).all()

    def get_candidates_by_job_paginated(self, **kwargs) -> tuple[list[Candidate], int]:
        items, total = _get_candidates_by_job_paginated(self.db, **kwargs)
        self._review_map = build_review_map(self.db, items)
        return items, total

    def get_finalized_candidates(self, **kwargs) -> tuple[list[Candidate], int]:
        return _get_finalized_candidates(self.db, **kwargs)

    def get_by_candidate_id(self, candidate_id: int) -> Candidate | None:
        return self.db.query(Candidate).filter(Candidate.id == candidate_id).first()

    def get_final_verdict(self, candidate_id: int) -> str | None:
        candidate = self.get_by_candidate_id(candidate_id)
        return candidate.final_verdict if candidate else None

    def to_candidate_dict(self, candidate: Candidate) -> dict:
        ai_review = get_ai_review(self.db, candidate, self._review_map)
        return build_candidate_response(candidate, ai_review)

    def create_queued_candidate(self, application_id: str, job_id: str, **kwargs) -> Candidate:
        return _mut.create_queued_candidate(self.db, application_id, job_id, **kwargs)

    def mark_processing(self, candidate: Candidate) -> Candidate:
        return _mut.mark_processing(self.db, candidate)

    def mark_result(self, candidate: Candidate, status, **kwargs) -> Candidate:
        return _mut.mark_result(self.db, candidate, status, **kwargs)

    def set_current_round_id(self, candidate: Candidate, round_id: UUID) -> Candidate:
        return _mut.set_current_round_id(self.db, candidate, round_id)

    def set_final_verdict(self, candidate_id: int, verdict: str) -> Candidate | None:
        return _mut.set_final_verdict(self.db, candidate_id, verdict)

    def update_status(self, candidate_id: int, new_status: str) -> Candidate | None:
        return _mut.update_status(self.db, candidate_id, new_status)

    def apply_transition(self, candidate_id: int, final_verdict: str | None = None, status: str | None = None) -> Candidate | None:
        return _mut.apply_transition(self.db, candidate_id, final_verdict, status)

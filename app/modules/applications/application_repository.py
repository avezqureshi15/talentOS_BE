from uuid import UUID

from sqlalchemy import String, cast
from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.modules.applications import application_repository_mutations as _mut
from app.modules.applications.application_repository_queries import (
    get_candidates_by_job_paginated as _get_candidates_by_job_paginated,
    get_finalized_candidates as _get_finalized_candidates,
    build_disqualified_by_map as _build_disqualified_by_map,
)
from app.modules.applications.application_response import build_candidate_response
from app.modules.evaluations.evaluation_model import Candidate
from app.modules.events.event_repository import EventRepository
from app.modules.hiring_requests.hiring_request_model import HiringRequest
from app.modules.interviews.models.interview import Interview
from app.modules.interviews.models.round_interviewer import RoundInterviewer
from app.modules.rounds.round_model import Round
from app.modules.users.user_model import User

logger = get_logger(__name__)


class ApplicationRepository:
    def __init__(self, db: Session):
        self.db = db

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
        return _get_candidates_by_job_paginated(self.db, **kwargs)

    def get_finalized_candidates(self, **kwargs) -> tuple[list[Candidate], int]:
        return _get_finalized_candidates(self.db, **kwargs)

    def get_by_candidate_id(self, candidate_id: int) -> Candidate | None:
        return self.db.query(Candidate).filter(Candidate.id == candidate_id).first()

    def get_final_verdict(self, candidate_id: int) -> str | None:
        candidate = self.get_by_candidate_id(candidate_id)
        return candidate.final_verdict if candidate else None

    def build_events_map(self, candidates: list[Candidate], ai: bool = False) -> dict[int, list[dict]]:
        if not ai or not candidates:
            return {}
        event_repo = EventRepository(self.db)
        raw = event_repo.get_by_candidate_ids([c.id for c in candidates])
        result: dict[int, list[dict]] = {}
        for cid, events in raw.items():
            result[cid] = [
                {"event_name": e.event_name, "created_at": e.created_at.isoformat(), "actor_type": e.actor_type}
                for e in events
            ]
        return result

    def build_disqualified_by_map(self, candidates: list[Candidate]) -> dict[int, list[str]]:
        return _build_disqualified_by_map(self.db, candidates)

    def attach_interview_data(self, candidates: list[Candidate]) -> None:
        round_ids = [str(c.current_round_id) for c in candidates if c.current_round_id]
        if not round_ids:
            return
        logger.warning("attach_interview_data: round_ids_str=%s", round_ids)
        rows = (
            self.db.query(Interview, Round, RoundInterviewer, User)
            .join(Round, Interview.round_id == Round.id)
            .join(RoundInterviewer, Round.id == RoundInterviewer.round_id)
            .join(User, RoundInterviewer.employee_id == User.id)
            .filter(cast(Interview.round_id, String).in_(round_ids))
            .all()
        )
        logger.warning("attach_interview_data: rows_found=%d", len(rows))
        interview_by_round: dict[str, dict] = {}
        for interview, round_, ri, user in rows:
            rid = str(interview.round_id)
            if rid not in interview_by_round:
                interview_by_round[rid] = {
                    "interview_id": str(interview.id),
                    "interviewer_emp_id": str(ri.employee_id),
                    "interviewer_name": user.name,
                    "round_name": round_.name or "",
                }
        for c in candidates:
            rid = str(c.current_round_id) if c.current_round_id else None
            if rid and rid in interview_by_round:
                c._interview_data = interview_by_round[rid]

    def to_candidate_dict(
        self,
        candidate: Candidate,
        ai: bool = False,
        events_map: dict[int, list[dict]] | None = None,
        disqualified_by: list[str] | None = None,
    ) -> dict:
        events = events_map.get(candidate.id) if events_map else None
        interview_data = getattr(candidate, '_interview_data', None)
        return build_candidate_response(
            candidate,
            hide_cover_letter=ai,
            events=events,
            disqualified_by=disqualified_by,
            interview_data=interview_data,
        )

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

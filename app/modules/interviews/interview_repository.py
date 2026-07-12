from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy.orm import Session

from app.core.logger import get_logger

logger = get_logger(__name__)

_INCOMING = "incoming"
_COMPLETED = "completed"


class InterviewRepositoryProtocol(Protocol):
    def list_paginated(
        self,
        status_filter: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[dict], int]: ...

    @staticmethod
    def build_pagination(page: int, per_page: int, total: int) -> dict: ...


class InterviewRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_paginated(
        self,
        status_filter: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[dict], int]:
        from app.modules.evaluations.evaluation_model import Candidate
        from app.modules.hiring_requests.hiring_request_model import HiringRequest
        from app.modules.interviews.models.interview import Interview
        from app.modules.rounds.round_model import Round
        from app.modules.users.user_model import User as Interviewer

        now = datetime.now(timezone.utc)

        query = (
            self.db.query(
                Interview.id,
                Interview.start_time,
                Interview.end_time,
                Interview.event_id,
                Round.jd_id,
                Round.candidate_id,
                Interviewer.emp_id,
                Interviewer.name.label("interviewer_name"),
                Interviewer.email.label("interviewer_email"),
                Candidate.candidate_name,
                Candidate.candidate_email,
                Candidate.external_application_id,
                HiringRequest.title.label("position_title"),
            )
            .join(Round, Interview.round_id == Round.id)
            .join(Interviewer, Interview.interviewer_id == Interviewer.id)
            .outerjoin(Candidate, Round.candidate_id == Candidate.id)
            .outerjoin(HiringRequest, Round.jd_id == HiringRequest.id)
        )

        if status_filter == _INCOMING:
            query = query.filter(Interview.start_time >= now)
        elif status_filter == _COMPLETED:
            query = query.filter(Interview.start_time < now)

        total = query.count()
        rows = (
            query.order_by(Interview.start_time.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        return [self._row_to_item(row, now) for row in rows], total

    def _row_to_item(self, row, now: datetime) -> dict:
        return {
            "id": str(row.id),
            "status": _COMPLETED if start < now else _INCOMING,
            "position": {
                "id": str(row.jd_id) if row.jd_id else "",
                "title": row.position_title or "",
            },
            "interviewer": {
                "id": row.emp_id or "",
                "name": row.interviewer_name or "",
                "email": row.interviewer_email or "",
            },
            "candidate": {
                "id": row.external_application_id or str(row.candidate_id or ""),
                "name": row.candidate_name,
                "email": row.candidate_email,
            },
            "schedule": {
                "start_time": start.isoformat() if start else None,
                "end_time": row.end_time.isoformat() if row.end_time else None,
                "timezone": "UTC",
            },
            "meeting": {
                "platform": "Google Meet" if row.event_id else None,
                "url": None,
            },
        }

    @staticmethod
    def build_pagination(page: int, per_page: int, total: int) -> dict:
        return {
            "current_page": page,
            "per_page": per_page,
            "total_records": total,
            "has_more": (page * per_page) < total,
        }
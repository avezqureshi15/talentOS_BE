import uuid
from datetime import datetime, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.constants import InterviewStatus
from app.core.logger import get_logger
from app.modules.evaluations.evaluation_model import Candidate
from app.modules.hiring_requests.hiring_request_model import HiringRequest
from app.modules.interviews.models.interview import Interview
from app.modules.interviews.models.round_interviewer import RoundInterviewer
from app.modules.rounds.round_model import Round
from app.modules.slots.slot_model import Slot
from app.modules.users.user_model import User

logger = get_logger(__name__)

_INCOMING = "incoming"
_COMPLETED = "completed"
_CANCELLED = "cancelled"


class InterviewQueryRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_paginated(
        self,
        status_filter: str | None = None,
        search: str | None = None,
        page: int = 1,
        per_page: int = 20,
        candidate_id: int | None = None,
        hiring_request_id: str | None = None,
    ) -> tuple[list[dict], int]:
        now = datetime.now(timezone.utc)
        query = (
            self.db.query(
                Interview.id,
                Interview.status.label("interview_status"),
                Interview.updated_at.label("cancelled_at"),
                Slot.start_at,
                Slot.end_at,
                Interview.event_id,
                Interview.meet_link,
                Round.jd_id,
                Round.candidate_id,
                User.id.label("interviewer_user_id"),
                User.emp_id,
                User.name.label("interviewer_name"),
                User.email.label("interviewer_email"),
                Candidate.candidate_name,
                Candidate.candidate_email,
                Candidate.external_application_id,
                HiringRequest.title.label("position_title"),
                Round.name.label("round_name"),
            )
            .join(Round, Interview.round_id == Round.id)
            .join(RoundInterviewer, RoundInterviewer.round_id == Round.id)
            .join(User, RoundInterviewer.employee_id == User.id)
            .join(Slot, Interview.slot_id == Slot.id)
            .outerjoin(Candidate, Round.candidate_id == Candidate.id)
            .outerjoin(HiringRequest, Round.jd_id == HiringRequest.id)
        )
        if candidate_id is not None:
            query = query.filter(Round.candidate_id == candidate_id)
        if hiring_request_id:
            query = query.filter(Round.jd_id == uuid.UUID(hiring_request_id))
        if status_filter == _CANCELLED:
            query = query.filter(Interview.status == InterviewStatus.CANCELLED.value)
        else:
            query = query.filter(Interview.status != InterviewStatus.CANCELLED.value)
            if status_filter == _INCOMING:
                query = query.filter(Slot.start_at >= now)
            elif status_filter == _COMPLETED:
                query = query.filter(Slot.start_at < now)
        if search:
            pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Round.name.ilike(pattern),
                    HiringRequest.title.ilike(pattern),
                    Candidate.candidate_name.ilike(pattern),
                    User.name.ilike(pattern),
                )
            )
        total = query.count()
        rows = (
            query.order_by(Slot.start_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return [self._row_to_item(row, now) for row in rows], total

    def get_by_id(self, interview_id: uuid.UUID) -> dict | None:
        now = datetime.now(timezone.utc)
        row = (
            self.db.query(
                Interview.id,
                Interview.status.label("interview_status"),
                Interview.updated_at.label("cancelled_at"),
                Slot.start_at,
                Slot.end_at,
                Interview.event_id,
                Interview.meet_link,
                Round.jd_id,
                Round.candidate_id,
                User.id.label("interviewer_user_id"),
                User.emp_id,
                User.name.label("interviewer_name"),
                User.email.label("interviewer_email"),
                Candidate.candidate_name,
                Candidate.candidate_email,
                Candidate.external_application_id,
                HiringRequest.title.label("position_title"),
                Round.name.label("round_name"),
            )
            .join(Round, Interview.round_id == Round.id)
            .join(RoundInterviewer, RoundInterviewer.round_id == Round.id)
            .join(User, RoundInterviewer.employee_id == User.id)
            .join(Slot, Interview.slot_id == Slot.id)
            .outerjoin(Candidate, Round.candidate_id == Candidate.id)
            .outerjoin(HiringRequest, Round.jd_id == HiringRequest.id)
            .filter(Interview.id == interview_id)
            .first()
        )
        if not row:
            return None
        return self._row_to_item(row, now)

    def _row_to_item(self, row, now: datetime) -> dict:
        start = row.start_at
        return {
            "id": str(row.id),
            "status": _COMPLETED if start and start < now else _INCOMING,
            "interview_status": row.interview_status or "",
            "position": {
                "id": str(row.jd_id) if row.jd_id else "",
                "title": row.position_title or "",
            },
            "interviewer": {
                "id": str(row.interviewer_user_id) if row.interviewer_user_id else "",
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
                "end_time": row.end_at.isoformat() if row.end_at else None,
                "timezone": "UTC",
            },
            "round_name": row.round_name or "",
            "cancelled_at": row.cancelled_at.isoformat() if row.cancelled_at else None,
            "meeting": {
                "platform": "Google Meet" if row.event_id else None,
                "url": row.meet_link,
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

import uuid
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.modules.interviews.models.interview import Interview

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

    def create(self, interview: Interview) -> Interview: ...
    def get_by_id(self, interview_id: uuid.UUID) -> Interview | None: ...
    def update_status(self, interview_id: uuid.UUID, status: str) -> None: ...
    def update_slot(self, interview_id: uuid.UUID, slot_id: uuid.UUID) -> None: ...


class InterviewRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, interview: Interview) -> Interview:
        logger.info("Creating interview record: round_id=%s", interview.round_id)
        self.db.add(interview)
        self.db.flush()
        return interview

    def get_by_id(self, interview_id: uuid.UUID) -> Interview | None:
        logger.info("Fetching interview by id: interview_id=%s", interview_id)
        obj = self.db.query(Interview).filter(Interview.id == interview_id).first()
        if obj is None:
            logger.warning("Interview not found in DB: interview_id=%s", interview_id)
        return obj

    def update_status(self, interview_id: uuid.UUID, status: str) -> None:
        logger.info("Updating interview status: id=%s | status=%s", interview_id, status)
        self.db.query(Interview).filter(Interview.id == interview_id).update(
            {"status": status}
        )
        self.db.flush()

    def update_slot(self, interview_id: uuid.UUID, slot_id: uuid.UUID) -> None:
        logger.info("Updating interview slot: id=%s | slot_id=%s", interview_id, slot_id)
        self.db.query(Interview).filter(Interview.id == interview_id).update(
            {"slot_id": slot_id}
        )
        self.db.flush()

    def list_paginated(
        self,
        status_filter: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[dict], int]:
        from app.modules.evaluations.evaluation_model import Candidate
        from app.modules.hiring_requests.hiring_request_model import HiringRequest
        from app.modules.interviews.models.interview import Interview
        from app.modules.interviews.models.round_interviewer import RoundInterviewer
        from app.modules.rounds.round_model import Round
        from app.modules.slots.slot_model import Slot
        from app.modules.users.user_model import User as Interviewer

        now = datetime.now(timezone.utc)

        query = (
            self.db.query(
                Interview.id,
                Slot.start_at,
                Slot.end_at,
                Interview.event_id,
                Interview.meet_link,
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
            .join(RoundInterviewer, RoundInterviewer.round_id == Round.id)
            .join(Interviewer, RoundInterviewer.employee_id == Interviewer.id)
            .join(Slot, Interview.slot_id == Slot.id)
            .outerjoin(Candidate, Round.candidate_id == Candidate.id)
            .outerjoin(HiringRequest, Round.jd_id == HiringRequest.id)
        )

        if status_filter == _INCOMING:
            query = query.filter(Slot.start_at >= now)
        elif status_filter == _COMPLETED:
            query = query.filter(Slot.start_at < now)

        total = query.count()
        rows = (
            query.order_by(Slot.start_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        return [self._row_to_item(row, now) for row in rows], total

    def _row_to_item(self, row, now: datetime) -> dict:
        start = row.start_at
        return {
            "id": str(row.id),
            "status": _COMPLETED if start and start < now else _INCOMING,
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
                "end_time": row.end_at.isoformat() if row.end_at else None,
                "timezone": "UTC",
            },
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

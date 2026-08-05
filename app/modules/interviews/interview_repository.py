import uuid
from typing import Protocol

from sqlalchemy.orm import Session

from app.core.constants import get_pipeline_stage
from app.core.logger import get_logger
from app.modules.evaluations.evaluation_model import Candidate
from app.modules.hiring_requests.hiring_request_model import HiringRequest
from sqlalchemy import and_
from app.modules.interviews.models.interview import Interview
from app.modules.interviews.models.round_interviewer import RoundInterviewer
from app.modules.rounds.round_model import Round
from app.modules.slots.slot_model import Slot
from app.modules.users.user_model import User

logger = get_logger(__name__)


class InterviewRepositoryProtocol(Protocol):
    def create(self, interview: Interview) -> Interview: ...
    def get_by_id(self, interview_id: uuid.UUID) -> Interview | None: ...
    def get_by_meet_link(self, meet_url: str) -> Interview | None: ...
    def get_by_round_id(self, round_id: uuid.UUID) -> Interview | None: ...
    def update_status(self, interview_id: uuid.UUID, status: str) -> None: ...
    def update_slot(self, interview_id: uuid.UUID, slot_id: uuid.UUID) -> None: ...
    def get_round_by_id(self, round_id: uuid.UUID) -> Round | None: ...
    def get_slot_by_id(self, slot_id: uuid.UUID) -> Slot | None: ...
    def get_candidate_by_id(self, candidate_id: int) -> Candidate | None: ...
    def get_hiring_request_by_id(self, hr_id: uuid.UUID) -> HiringRequest | None: ...
    def get_interviewer_emails_for_round(self, round_id: uuid.UUID) -> list[str]: ...
    def update_slot_status(self, slot_id: uuid.UUID | None, status: str) -> None: ...
    def create_round(self, name: str, candidate_id: int, jd_id: uuid.UUID, slot_id: uuid.UUID, round_type: str | None = None) -> Round: ...
    def create_round_interviewer(self, round_id: uuid.UUID, employee_id: int) -> RoundInterviewer: ...
    def update_candidate_status(self, candidate_id: int, status: str) -> None: ...
    def save_review_questions(
        self,
        interview_id: uuid.UUID,
        transcript_text: str | None,
        review_questions: dict | None,
        source: str | None,
    ) -> None: ...


class InterviewRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, interview: Interview) -> Interview:
        logger.info("Creating interview: round_id=%s", interview.round_id)
        self.db.add(interview)
        self.db.flush()
        return interview

    def get_by_id(self, interview_id: uuid.UUID) -> Interview | None:
        logger.debug("Fetching interview: id=%s", interview_id)
        return self.db.query(Interview).filter(Interview.id == interview_id).first()

    def get_by_meet_link(self, meet_url: str) -> Interview | None:
        normalized = (meet_url or "").strip().rstrip("/")
        if not normalized:
            return None
        interview = (
            self.db.query(Interview)
            .filter(Interview.meet_link == normalized)
            .order_by(Interview.created_at.desc())
            .first()
        )
        if interview:
            return interview
        # Tolerate stored link with/without trailing slash
        return (
            self.db.query(Interview)
            .filter(Interview.meet_link == f"{normalized}/")
            .order_by(Interview.created_at.desc())
            .first()
        )

    def get_by_round_id(self, round_id: uuid.UUID) -> Interview | None:
        """Latest non-cancelled interview for the round; else latest overall."""
        from app.core.constants import InterviewStatus

        non_cancelled = (
            self.db.query(Interview)
            .filter(
                Interview.round_id == round_id,
                Interview.status != InterviewStatus.CANCELLED.value,
            )
            .order_by(Interview.created_at.desc())
            .first()
        )
        if non_cancelled:
            return non_cancelled
        return (
            self.db.query(Interview)
            .filter(Interview.round_id == round_id)
            .order_by(Interview.created_at.desc())
            .first()
        )

    def update_status(self, interview_id: uuid.UUID, status: str) -> None:
        logger.info("Updating interview status: id=%s | status=%s", interview_id, status)
        self.db.query(Interview).filter(Interview.id == interview_id).update({"status": status})
        self.db.flush()

    def update_slot(self, interview_id: uuid.UUID, slot_id: uuid.UUID) -> None:
        logger.info("Updating interview slot: id=%s | slot_id=%s", interview_id, slot_id)
        self.db.query(Interview).filter(Interview.id == interview_id).update({"slot_id": slot_id})
        self.db.flush()

    def get_round_by_id(self, round_id: uuid.UUID) -> Round | None:
        return self.db.query(Round).filter(Round.id == round_id).first()

    def get_slot_by_id(self, slot_id: uuid.UUID) -> Slot | None:
        return self.db.query(Slot).filter(Slot.id == slot_id).first()

    def get_candidate_by_id(self, candidate_id: int) -> Candidate | None:
        return self.db.query(Candidate).filter(Candidate.id == candidate_id).first()

    def get_hiring_request_by_id(self, hr_id: uuid.UUID) -> HiringRequest | None:
        return self.db.query(HiringRequest).filter(HiringRequest.id == hr_id).first()

    def get_interviewer_emails_for_round(self, round_id: uuid.UUID) -> list[str]:
        join_on = and_(
            User.employee_id == RoundInterviewer.employee_id,
            User.employee_id.isnot(None),
        )
        emails = [
            u.email
            for u in self.db.query(User)
            .join(RoundInterviewer, join_on)
            .filter(RoundInterviewer.round_id == round_id)
            .all()
            if u.email
        ]
        logger.info("Found %d interviewer(s) for round_id=%s", len(emails), round_id)
        return emails

    def update_slot_status(self, slot_id: uuid.UUID | None, status: str) -> None:
        if slot_id is not None:
            self.db.query(Slot).filter(Slot.id == slot_id).update({"status": status})
            self.db.flush()

    def create_round(self, name: str, candidate_id: int, jd_id: uuid.UUID, slot_id: uuid.UUID, round_type: str | None = None) -> Round:
        r = Round(name=name, round_type=round_type, candidate_id=candidate_id, jd_id=jd_id, slot_id=slot_id)
        self.db.add(r)
        self.db.flush()
        return r

    def create_round_interviewer(self, round_id: uuid.UUID, employee_id: int) -> RoundInterviewer:
        # ``employee_id`` is a real employees.id post-Phase-3 (the FE picker
        # sources it from /employees/). Stored directly, no translation.
        ri = RoundInterviewer(round_id=round_id, employee_id=employee_id)
        self.db.add(ri)
        self.db.flush()
        return ri

    def update_candidate_status(self, candidate_id: int, status: str) -> None:
        logger.info("Updating candidate status: id=%s | status=%s", candidate_id, status)
        self.db.query(Candidate).filter(Candidate.id == candidate_id).update({"status": status, "stage": get_pipeline_stage(status)})
        self.db.flush()

    def save_review_questions(
        self,
        interview_id: uuid.UUID,
        transcript_text: str | None,
        review_questions: dict | None,
        source: str | None,
    ) -> None:
        logger.info(
            "Saving review questions | interview_id=%s source=%s",
            interview_id,
            source,
        )
        self.db.query(Interview).filter(Interview.id == interview_id).update(
            {
                "transcript_text": transcript_text,
                "review_questions": review_questions,
                "review_questions_source": source,
            }
        )
        self.db.flush()

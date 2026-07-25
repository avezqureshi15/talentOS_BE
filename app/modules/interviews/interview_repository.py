import uuid
from typing import Protocol

from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.modules.evaluations.evaluation_model import Candidate
from app.modules.hiring_requests.hiring_request_model import HiringRequest
from app.modules.interviews.models.interview import Interview
from app.modules.interviews.models.round_interviewer import RoundInterviewer
from app.modules.rounds.round_model import Round
from app.modules.slots.slot_model import Slot
from app.modules.users.user_model import User

logger = get_logger(__name__)


class InterviewRepositoryProtocol(Protocol):
    def create(self, interview: Interview) -> Interview: ...
    def get_by_id(self, interview_id: uuid.UUID) -> Interview | None: ...
    def update_status(self, interview_id: uuid.UUID, status: str) -> None: ...
    def update_slot(self, interview_id: uuid.UUID, slot_id: uuid.UUID) -> None: ...
    def get_round_by_id(self, round_id: uuid.UUID) -> Round | None: ...
    def get_slot_by_id(self, slot_id: uuid.UUID) -> Slot | None: ...
    def get_candidate_by_id(self, candidate_id: int) -> Candidate | None: ...
    def get_hiring_request_by_id(self, hr_id: uuid.UUID) -> HiringRequest | None: ...
    def get_interviewer_emails_for_round(self, round_id: uuid.UUID) -> list[str]: ...
    def update_slot_status(self, slot_id: uuid.UUID | None, status: str) -> None: ...
    def create_round(self, name: str, candidate_id: int, jd_id: uuid.UUID, slot_id: uuid.UUID) -> Round: ...
    def create_round_interviewer(self, round_id: uuid.UUID, employee_id: int) -> RoundInterviewer: ...
    def update_candidate_status(self, candidate_id: int, status: str) -> None: ...


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
        emails = [u.email for u in
                  self.db.query(User).join(RoundInterviewer, RoundInterviewer.employee_id == User.id)
                  .filter(RoundInterviewer.round_id == round_id).all() if u.email]
        logger.info("Found %d interviewer(s) for round_id=%s", len(emails), round_id)
        return emails

    def update_slot_status(self, slot_id: uuid.UUID | None, status: str) -> None:
        if slot_id is not None:
            self.db.query(Slot).filter(Slot.id == slot_id).update({"status": status})
            self.db.flush()

    def create_round(self, name: str, candidate_id: int, jd_id: uuid.UUID, slot_id: uuid.UUID) -> Round:
        r = Round(name=name, candidate_id=candidate_id, jd_id=jd_id, slot_id=slot_id)
        self.db.add(r)
        self.db.flush()
        return r

    def create_round_interviewer(self, round_id: uuid.UUID, employee_id: int) -> RoundInterviewer:
        ri = RoundInterviewer(round_id=round_id, employee_id=employee_id)
        self.db.add(ri)
        self.db.flush()
        return ri

    def update_candidate_status(self, candidate_id: int, status: str) -> None:
        logger.info("Updating candidate status: id=%s | status=%s", candidate_id, status)
        self.db.query(Candidate).filter(Candidate.id == candidate_id).update({"status": status})
        self.db.flush()

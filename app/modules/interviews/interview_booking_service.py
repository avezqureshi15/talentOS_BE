import uuid

from sqlalchemy.orm import Session

from app.common.exceptions.application_exception import ApplicationNotFoundException, CandidateFinalizedException
from app.common.exceptions.slot_exception import SlotNotFoundException
from app.core.logger import get_logger
from app.modules.evaluations.evaluation_model import Candidate
from app.modules.interviews.interview_schedule_service import InterviewScheduleService
from app.modules.interviews.interview_schema import BookInterviewRequest, ScheduleInterviewResponse
from app.modules.interviews.models.round_interviewer import RoundInterviewer
from app.modules.rounds.round_model import Round
from app.modules.slots.slot_model import Slot

logger = get_logger(__name__)


class BookingService:
    def __init__(self, db: Session):
        self.db = db
        self._schedule_svc = InterviewScheduleService(db)

    def book_interview(self, data: BookInterviewRequest) -> ScheduleInterviewResponse:
        logger.info(
            "Booking interview: candidate_id=%s | slot_id=%s | round_name=%s | interviewers=%s | gmeet=%s",
            data.candidate_id, data.slot_id, data.round_name, data.interviewer_ids, data.create_google_meet,
        )

        candidate = self.db.query(Candidate).filter(Candidate.id == data.candidate_id).first()
        if not candidate:
            logger.warning("Candidate not found: candidate_id=%s", data.candidate_id)
            raise ApplicationNotFoundException(data.candidate_id)
        if candidate.final_verdict is not None:
            logger.warning("Candidate already finalized: id=%s | verdict=%s", data.candidate_id, candidate.final_verdict)
            raise CandidateFinalizedException(data.candidate_id, candidate.final_verdict)

        slot = self.db.query(Slot).filter(Slot.id == uuid.UUID(data.slot_id)).first()
        if not slot:
            raise SlotNotFoundException(data.slot_id)

        round_obj = Round(
            name=data.round_name,
            candidate_id=data.candidate_id,
            jd_id=uuid.UUID(data.jd_id),
            slot_id=uuid.UUID(data.slot_id),
        )
        self.db.add(round_obj)
        self.db.flush()
        logger.info("Round created: id=%s | name=%s", round_obj.id, data.round_name)

        for emp_id in data.interviewer_ids:
            ri = RoundInterviewer(round_id=round_obj.id, employee_id=emp_id)
            self.db.add(ri)
        self.db.flush()
        logger.info("Assigned %d interviewer(s) to round_id=%s", len(data.interviewer_ids), round_obj.id)

        result = self._schedule_svc.schedule_interview(
            round_id=round_obj.id,
            slot_id=uuid.UUID(data.slot_id),
            create_google_meet=data.create_google_meet,
            commit=False,
        )
        self.db.commit()
        logger.info("Interview booked successfully: id=%s | round_id=%s", result.id, result.round_id)
        return result

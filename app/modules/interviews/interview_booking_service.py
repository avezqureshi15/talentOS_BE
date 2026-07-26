import uuid

from sqlalchemy.orm import Session

from app.common.exceptions.application_exception import ApplicationNotFoundException, CandidateFinalizedException
from app.common.exceptions.slot_exception import SlotNotFoundException
from app.core.logger import get_logger
from app.modules.interviews.interview_repository import InterviewRepository, InterviewRepositoryProtocol
from app.modules.interviews.interview_schedule_service import InterviewScheduleService, EventServiceProtocol
from app.modules.interviews.interview_schema import BookInterviewRequest, ScheduleInterviewResponse

logger = get_logger(__name__)


class BookingService:
    def __init__(self, db: Session, repo: InterviewRepositoryProtocol | None = None, event_service: EventServiceProtocol | None = None):
        self.db = db
        self.repository = repo or InterviewRepository(db)
        self._schedule_svc = InterviewScheduleService(db, event_service=event_service)

    def book_interview(self, data: BookInterviewRequest) -> ScheduleInterviewResponse:
        logger.info("Booking: candidate=%s | slot=%s | round=%s | interviewers=%d | gmeet=%s",
                    data.candidate_id, data.slot_id, data.round_name,
                    len(data.interviewer_ids), data.create_google_meet)

        candidate = self.repository.get_candidate_by_id(data.candidate_id)
        if not candidate:
            raise ApplicationNotFoundException(data.candidate_id)
        if candidate.final_verdict is not None:
            raise CandidateFinalizedException(data.candidate_id, candidate.final_verdict)

        slot = self.repository.get_slot_by_id(uuid.UUID(data.slot_id))
        if not slot:
            raise SlotNotFoundException(data.slot_id)

        round_obj = self.repository.create_round(
            name=data.round_name, round_type=data.round_type,
            candidate_id=data.candidate_id,
            jd_id=uuid.UUID(data.jd_id), slot_id=uuid.UUID(data.slot_id),
        )
        for emp_id in data.interviewer_ids:
            self.repository.create_round_interviewer(round_id=round_obj.id, employee_id=emp_id)

        candidate.current_round_id = round_obj.id
        self.db.flush()

        result = self._schedule_svc.schedule_interview(
            round_id=round_obj.id, slot_id=uuid.UUID(data.slot_id),
            create_google_meet=data.create_google_meet, commit=False,
        )
        self.db.commit()
        logger.info("Booked: id=%s | round=%s", result.id, result.round_id)
        return result

import uuid

from google.api_core.exceptions import GoogleAPICallError
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from app.common.exceptions.calendar_exception import CalendarApiFailedException, CalendarNotConfiguredException
from app.common.exceptions.interview_exception import InterviewNotFoundException
from app.common.exceptions.round_exception import RoundNotFoundException
from app.common.exceptions.slot_exception import SlotNotFoundException
from app.common.schemas.calendar_schema import CalendarEventResponse
from app.common.services.google_calendar_service import GoogleCalendarService
from app.core.config import settings
from app.core.logger import get_logger
from app.modules.evaluations.evaluation_model import Candidate
from app.modules.hiring_requests.hiring_request_model import HiringRequest
from app.modules.interviews.interview_repository import InterviewRepository, InterviewRepositoryProtocol
from app.modules.interviews.interview_schema import CancelInterviewResponse, ScheduleInterviewResponse
from app.modules.interviews.models.interview import Interview
from app.modules.interviews.models.round_interviewer import RoundInterviewer
from app.modules.rounds.round_model import Round
from app.modules.slots.slot_model import Slot, SlotStatus
from app.modules.users.user_model import User

logger = get_logger(__name__)


class InterviewScheduleService:
    def __init__(self, db: Session, repo: InterviewRepositoryProtocol | None = None):
        self.db = db
        self.repository = repo or InterviewRepository(db)

    def _get_calendar_service(self) -> GoogleCalendarService:
        path = settings.GOOGLE_SERVICE_ACCOUNT_JSON.strip()
        email = settings.GOOGLE_IMPERSONATION_EMAIL.strip()
        if not (path and email):
            raise CalendarNotConfiguredException()
        return GoogleCalendarService(service_account_path=path, impersonation_email=email, timezone=settings.GOOGLE_CALENDAR_TIMEZONE)

    def _interviewer_emails(self, round_id: uuid.UUID) -> list[str]:
        emails = [
            u.email for u in
            self.db.query(User).join(RoundInterviewer, RoundInterviewer.employee_id == User.id)
            .filter(RoundInterviewer.round_id == round_id).all()
            if u.email
        ]
        if not emails:
            logger.warning("No interviewers found for round_id=%s — event will have no interviewer attendees", round_id)
        else:
            logger.info("Found %d interviewer(s) for round_id=%s", len(emails), round_id)
        return emails

    def _set_slot_status(self, slot_id: uuid.UUID | None, status: str) -> None:
        if slot_id is None:
            logger.debug("_set_slot_status called with slot_id=None — skipping")
            return
        rows = self.db.query(Slot).filter(Slot.id == slot_id).update({"status": status})
        self.db.flush()
        if rows == 0:
            logger.warning("Slot status update affected 0 rows: slot_id=%s | status=%s", slot_id, status)
        else:
            logger.info("Slot status updated: slot_id=%s | status=%s", slot_id, status)

    def schedule_interview(
        self,
        round_id: uuid.UUID,
        slot_id: uuid.UUID,
        create_google_meet: bool = True,
        commit: bool = True,
    ) -> ScheduleInterviewResponse:
        logger.info("Scheduling interview: round_id=%s | slot_id=%s | create_google_meet=%s", round_id, slot_id, create_google_meet)
        round_obj = self.db.query(Round).filter(Round.id == round_id).first()
        if not round_obj:
            logger.warning("Round not found: round_id=%s", round_id)
            raise RoundNotFoundException(str(round_id))
        slot = self.db.query(Slot).filter(Slot.id == slot_id).first()
        if not slot:
            logger.warning("Slot not found: slot_id=%s", slot_id)
            raise SlotNotFoundException(str(slot_id))
        candidate = self.db.query(Candidate).filter(Candidate.id == round_obj.candidate_id).first() if round_obj.candidate_id else None
        hiring_request = self.db.query(HiringRequest).filter(HiringRequest.id == round_obj.jd_id).first() if round_obj.jd_id else None
        title = f"Interview: {hiring_request.title}" if hiring_request else "Interview"
        if candidate and candidate.candidate_name:
            title += f" - {candidate.candidate_name}"
        logger.info("Calendar event title: %s | attendees: candidate=%s + %d interviewer(s)", title, candidate.candidate_email if candidate else "none", len(attendees := self._interviewer_emails(round_id)))
        if candidate and candidate.candidate_email:
            attendees.insert(0, candidate.candidate_email)
        calendar = self._get_calendar_service()
        try:
            result: CalendarEventResponse = calendar.create_meet(
                title=title, start=slot.start_at, end=slot.end_at,
                attendees=attendees, description=f"Interview: {round_obj.name or 'N/A'}",
                with_gmeet=create_google_meet,
            )
        except (HttpError, GoogleAPICallError) as exc:
            logger.error("Google Calendar API failed to create event: %s", exc)
            raise CalendarApiFailedException("Failed to create calendar event") from exc
        interview = Interview(
            round_id=round_id, slot_id=slot_id, event_id=result.event_id,
            meet_link=result.meet_link, status="SCHEDULED",
        )
        created = self.repository.create(interview)
        self._set_slot_status(slot_id, SlotStatus.BOOKED.value)
        if commit:
            self.db.commit()
            self.db.refresh(created)
        logger.info("Interview scheduled successfully: id=%s | event_id=%s | meet_link=%s", created.id, result.event_id, result.meet_link)
        return ScheduleInterviewResponse(
            id=str(created.id), round_id=str(created.round_id),
            slot_id=str(created.slot_id) if created.slot_id else None,
            event_id=created.event_id, meet_link=result.meet_link, status=created.status,
        )

    def reschedule_interview(self, interview_id: uuid.UUID, new_slot_id: uuid.UUID) -> ScheduleInterviewResponse:
        logger.info("Rescheduling interview: interview_id=%s | new_slot_id=%s", interview_id, new_slot_id)
        interview = self.repository.get_by_id(interview_id)
        if not interview:
            logger.warning("Interview not found: interview_id=%s", interview_id)
            raise InterviewNotFoundException(str(interview_id))
        new_slot = self.db.query(Slot).filter(Slot.id == new_slot_id).first()
        if not new_slot:
            logger.warning("New slot not found: slot_id=%s", new_slot_id)
            raise SlotNotFoundException(str(new_slot_id))
        old_slot_id = interview.slot_id
        logger.info("Reschedule: interview_id=%s | old_slot_id=%s | new_slot_id=%s | event_id=%s", interview_id, old_slot_id, new_slot_id, interview.event_id)
        if interview.event_id:
            try:
                self._get_calendar_service().update_event(
                    event_id=interview.event_id, start=new_slot.start_at, end=new_slot.end_at, with_gmeet=True,
                )
                logger.info("Calendar event updated for reschedule: event_id=%s", interview.event_id)
            except (HttpError, GoogleAPICallError) as exc:
                logger.error("Google Calendar API failed to update event: %s", exc)
                raise CalendarApiFailedException("Failed to update calendar event") from exc
        else:
            logger.warning("Reschedule skipped calendar update: interview_id=%s has no event_id", interview_id)
        self.repository.update_slot(interview_id, new_slot_id)
        self.repository.update_status(interview_id, "RESCHEDULED")
        self._set_slot_status(old_slot_id, SlotStatus.AVAILABLE.value)
        self._set_slot_status(new_slot_id, SlotStatus.BOOKED.value)
        self.db.commit()
        self.db.refresh(interview)
        logger.info("Interview rescheduled successfully: id=%s | new_slot_id=%s", interview.id, new_slot_id)
        return ScheduleInterviewResponse(
            id=str(interview.id), round_id=str(interview.round_id),
            slot_id=str(interview.slot_id) if interview.slot_id else None,
            event_id=interview.event_id, status=interview.status,
        )

    def cancel_interview(self, interview_id: uuid.UUID) -> CancelInterviewResponse:
        logger.info("Cancelling interview: interview_id=%s", interview_id)
        interview = self.repository.get_by_id(interview_id)
        if not interview:
            logger.warning("Interview not found: interview_id=%s", interview_id)
            raise InterviewNotFoundException(str(interview_id))
        logger.info("Cancel interview: id=%s | slot_id=%s | event_id=%s | current_status=%s", interview.id, interview.slot_id, interview.event_id, interview.status)
        if interview.event_id:
            try:
                self._get_calendar_service().cancel_event(event_id=interview.event_id)
                logger.info("Calendar event cancelled: event_id=%s", interview.event_id)
            except (HttpError, GoogleAPICallError) as exc:
                logger.error("Google Calendar API failed to cancel event: %s", exc)
                raise CalendarApiFailedException("Failed to cancel calendar event") from exc
        else:
            logger.warning("Cancel skipped calendar deletion: interview_id=%s has no event_id", interview_id)
        self._set_slot_status(interview.slot_id, SlotStatus.AVAILABLE.value)
        self.repository.update_status(interview_id, "CANCELLED")
        self.db.commit()
        self.db.refresh(interview)
        logger.info("Interview cancelled successfully: id=%s | status=%s", interview.id, interview.status)
        return CancelInterviewResponse(id=str(interview.id), status=interview.status)

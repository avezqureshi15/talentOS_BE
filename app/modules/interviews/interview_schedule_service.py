import uuid
from typing import Protocol

from google.api_core.exceptions import GoogleAPICallError
from googleapiclient.errors import HttpError
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.common.clients.meetmind_client import MeetMindClient
from app.common.exceptions.calendar_exception import CalendarApiFailedException
from app.common.exceptions.interview_exception import InterviewNotFoundException
from app.common.exceptions.round_exception import RoundNotFoundException
from app.common.exceptions.slot_exception import SlotNotFoundException
from app.core.config import settings
from app.core.constants import EvaluationStatus, InterviewStatus
from app.core.logger import get_logger
from app.cron.interview_fallback import (
    remove_interview_fallback,
    reschedule_interview_fallback,
    schedule_interview_fallback,
)
from app.cron.interview_ongoing import (
    remove_interview_ongoing,
    reschedule_interview_ongoing,
    schedule_interview_ongoing,
)
from app.modules.interviews.interview_helpers import get_calendar_service
from app.modules.interviews.interview_repository import InterviewRepository, InterviewRepositoryProtocol
from app.modules.interviews.interview_schema import CancelInterviewResponse, ScheduleInterviewResponse
from app.modules.interviews.models.interview import Interview
from app.modules.slots.slot_model import SlotStatus

logger = get_logger(__name__)


class _EventPayload(BaseModel):
    entity_type: str
    entity_id: str
    job_id: str | None = None
    candidate_id: int | None = None
    event_name: str
    state_code: str
    actor_type: str | None = None
    actor_id: str | None = None
    remark: str | None = None
    action_url: str | None = None
    action_label: str | None = None
    event_metadata: dict | None = None


class EventServiceProtocol(Protocol):
    def create_event(self, data: BaseModel) -> BaseModel: ...


class InterviewScheduleService:
    def __init__(self, db: Session, repo: InterviewRepositoryProtocol | None = None, event_service: EventServiceProtocol | None = None):
        self.db = db
        self.repository = repo or InterviewRepository(db)
        self.event_service = event_service

    def schedule_interview(
        self,
        round_id: uuid.UUID,
        slot_id: uuid.UUID,
        create_google_meet: bool = True,
        commit: bool = True,
    ) -> ScheduleInterviewResponse:
        logger.info("Scheduling interview: round_id=%s | slot_id=%s", round_id, slot_id)
        round_obj = self.repository.get_round_by_id(round_id)
        if not round_obj:
            raise RoundNotFoundException(str(round_id))
        slot = self.repository.get_slot_by_id(slot_id)
        if not slot:
            raise SlotNotFoundException(str(slot_id))
        candidate = self.repository.get_candidate_by_id(round_obj.candidate_id) if round_obj.candidate_id else None
        title = round_obj.name or "Interview"
        attendees = self.repository.get_interviewer_emails_for_round(round_id)
        if candidate and candidate.candidate_email:
            attendees.insert(0, candidate.candidate_email)
        try:
            result = get_calendar_service().create_meet(
                title=title, start=slot.start_at, end=slot.end_at,
                attendees=attendees, description=f"Interview: {round_obj.name or 'N/A'}",
                with_gmeet=create_google_meet,
            )
        except (HttpError, GoogleAPICallError) as exc:
            logger.error("Calendar API failed: %s", exc)
            raise CalendarApiFailedException("Failed to create calendar event") from exc
        created = self.repository.create(Interview(
            round_id=round_id, slot_id=slot_id, event_id=result.event_id,
            meet_link=result.meet_link, status=InterviewStatus.SCHEDULED.value,
        ))
        if round_obj.candidate_id:
            self.repository.update_candidate_status(round_obj.candidate_id, EvaluationStatus.INTERVIEW_SCHEDULED.value)
            if self.event_service:
                self.event_service.create_event(_EventPayload(
                    entity_type="CANDIDATE",
                    entity_id=str(round_obj.candidate_id),
                    event_name="Interview Scheduled",
                    state_code="INTERVIEW_SCHEDULED",
                    actor_type="HR",
                    candidate_id=round_obj.candidate_id,
                    action_url=result.meet_link,
                    action_label="Join Meeting",
                    event_metadata={
                        "round_id": str(round_id), "round_name": round_obj.name,
                        "slot_time": slot.start_at.isoformat() if hasattr(slot, "start_at") else None,
                        "interviewers": attendees,
                    },
                ))
            if round_obj.jd_id:
                from app.modules.notifications.notification_model import NotificationType
                from app.modules.notifications.notification_service import NotificationService

                NotificationService(self.db).notify_job_team_and_admins(
                    round_obj.jd_id,
                    notification_type=NotificationType.INTERVIEW_SCHEDULED.value,
                    title="Interview scheduled",
                    body=f"An interview for round \"{round_obj.name or round_id}\" is scheduled.",
                    action_url=result.meet_link,
                    action_label="Join meeting",
                    candidate_id=round_obj.candidate_id,
                    dedupe_key=f"INTERVIEW_SCHEDULED-{round_id}",
                )
        self.repository.update_slot_status(slot_id, SlotStatus.BOOKED.value)
        if commit:
            self.db.commit()
            self.db.refresh(created)

        if result.meet_link:
            MeetMindClient().schedule_meeting(
                meet_url=result.meet_link,
                title=title,
                participant_emails=attendees,
            )

        schedule_interview_fallback(str(created.id), slot.end_at)
        schedule_interview_ongoing(str(created.id), slot.start_at)
        logger.info(
            "Interview scheduled: id=%s | event_id=%s | fallback_in_seconds=%s",
            created.id,
            result.event_id,
            settings.INTERVIEW_FALLBACK_SECONDS,
        )
        return ScheduleInterviewResponse(
            id=str(created.id), round_id=str(created.round_id),
            slot_id=str(created.slot_id) if created.slot_id else None,
            event_id=created.event_id, meet_link=result.meet_link, status=created.status,
        )

    def reschedule_interview(self, interview_id: uuid.UUID, new_slot_id: uuid.UUID) -> ScheduleInterviewResponse:
        logger.info("Rescheduling interview: id=%s | new_slot=%s", interview_id, new_slot_id)
        interview = self.repository.get_by_id(interview_id)
        if not interview:
            raise InterviewNotFoundException(str(interview_id))
        new_slot = self.repository.get_slot_by_id(new_slot_id)
        if not new_slot:
            raise SlotNotFoundException(str(new_slot_id))
        old_slot_id = interview.slot_id
        if interview.event_id:
            try:
                get_calendar_service().update_event(
                    event_id=interview.event_id, start=new_slot.start_at, end=new_slot.end_at, with_gmeet=True,
                )
            except (HttpError, GoogleAPICallError) as exc:
                logger.error("Calendar update failed: %s", exc)
                raise CalendarApiFailedException("Failed to update calendar event") from exc
        self.repository.update_slot(interview_id, new_slot_id)
        self.repository.update_status(interview_id, InterviewStatus.RESCHEDULED.value)
        self.repository.update_slot_status(old_slot_id, SlotStatus.AVAILABLE.value)
        self.repository.update_slot_status(new_slot_id, SlotStatus.BOOKED.value)
        round_obj = self.repository.get_round_by_id(interview.round_id)
        if round_obj and round_obj.candidate_id:
            self.repository.update_candidate_status(round_obj.candidate_id, EvaluationStatus.INTERVIEW_RESCHEDULED.value)
        self.db.commit()
        self.db.refresh(interview)
        if round_obj and round_obj.candidate_id and self.event_service:
            self.event_service.create_event(_EventPayload(
                entity_type="CANDIDATE",
                entity_id=str(round_obj.candidate_id),
                event_name="Interview Rescheduled",
                state_code="INTERVIEW_RESCHEDULED",
                actor_type="HR",
                candidate_id=round_obj.candidate_id,
                event_metadata={"round_id": str(interview.round_id), "old_slot": str(old_slot_id), "new_slot": str(new_slot_id)},
            ))
        if round_obj and round_obj.jd_id:
            from app.modules.notifications.notification_model import NotificationType
            from app.modules.notifications.notification_service import NotificationService

            NotificationService(self.db).notify_job_team_and_admins(
                round_obj.jd_id,
                notification_type=NotificationType.INTERVIEW_SCHEDULED.value,
                title="Interview rescheduled",
                body=f"The interview for round \"{round_obj.name or interview.round_id}\" was rescheduled.",
                candidate_id=round_obj.candidate_id,
                dedupe_key=f"INTERVIEW_RESCHEDULED-{interview.id}",
            )
            self.db.commit()

        if interview.meet_link:
            attendees = self.repository.get_interviewer_emails_for_round(interview.round_id)
            title = round_obj.name if round_obj else "Interview"
            MeetMindClient().schedule_meeting(
                meet_url=interview.meet_link,
                title=title or "Interview",
                participant_emails=attendees,
            )

        reschedule_interview_fallback(str(interview.id), new_slot.end_at)
        reschedule_interview_ongoing(str(interview.id), new_slot.start_at)
        logger.info("Interview rescheduled: id=%s", interview.id)
        return ScheduleInterviewResponse(
            id=str(interview.id), round_id=str(interview.round_id),
            slot_id=str(interview.slot_id) if interview.slot_id else None,
            event_id=interview.event_id, status=interview.status,
        )

    def cancel_interview(self, interview_id: uuid.UUID) -> CancelInterviewResponse:
        logger.info("Cancelling interview: id=%s", interview_id)
        interview = self.repository.get_by_id(interview_id)
        if not interview:
            raise InterviewNotFoundException(str(interview_id))
        if interview.event_id:
            try:
                get_calendar_service().cancel_event(event_id=interview.event_id)
            except (HttpError, GoogleAPICallError) as exc:
                logger.error("Calendar cancel failed: %s", exc)
                raise CalendarApiFailedException("Failed to cancel calendar event") from exc
        self.repository.update_slot_status(interview.slot_id, SlotStatus.AVAILABLE.value)
        self.repository.update_status(interview_id, InterviewStatus.CANCELLED.value)
        round_obj = self.repository.get_round_by_id(interview.round_id)
        if round_obj and round_obj.candidate_id:
            self.repository.update_candidate_status(round_obj.candidate_id, EvaluationStatus.INTERVIEW_CANCELLED.value)
        self.db.commit()
        self.db.refresh(interview)
        if round_obj and round_obj.candidate_id and self.event_service:
            self.event_service.create_event(_EventPayload(
                entity_type="CANDIDATE",
                entity_id=str(round_obj.candidate_id),
                event_name="Interview Cancelled",
                state_code="INTERVIEW_CANCELLED",
                actor_type="HR",
                candidate_id=round_obj.candidate_id,
                event_metadata={"round_id": str(interview.round_id)},
            ))
        if round_obj and round_obj.jd_id:
            from app.modules.notifications.notification_model import NotificationType
            from app.modules.notifications.notification_service import NotificationService

            NotificationService(self.db).notify_job_team_and_admins(
                round_obj.jd_id,
                notification_type=NotificationType.INTERVIEW_SCHEDULED.value,
                title="Interview cancelled",
                body=f"The interview for round \"{round_obj.name or interview.round_id}\" was cancelled.",
                candidate_id=round_obj.candidate_id,
                dedupe_key=f"INTERVIEW_CANCELLED-{interview.id}",
            )
            self.db.commit()
        remove_interview_fallback(str(interview.id))
        remove_interview_ongoing(str(interview.id))
        logger.info("Interview cancelled: id=%s", interview.id)
        return CancelInterviewResponse(id=str(interview.id), status=interview.status)

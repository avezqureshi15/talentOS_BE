from uuid import UUID

from sqlalchemy.orm import Session

from app.common.exceptions.application_exception import (
    ApplicationNotFoundException,
    CandidateFinalizedException,
)
from app.core.constants import InterviewStatus
from app.core.logger import get_logger
from app.core.state_machine import TRANSITIONS
from app.modules.events.event_schema import EventCreate
from app.modules.events.event_service import EventService
from app.modules.applications.application_repository import ApplicationRepository
from app.modules.evaluations.evaluation_schema import EvaluationResponse

logger = get_logger(__name__)


class ApplicationStateService:
    def __init__(self, db: Session, repo: ApplicationRepository):
        self.db = db
        self.repo = repo

    def _resolve_round_candidate(self, round_id) -> int | None:
        from app.modules.rounds.round_model import Round

        rid = UUID(str(round_id)) if not isinstance(round_id, UUID) else round_id
        round_ = self.db.query(Round).filter(Round.id == rid).first()
        return round_.candidate_id if round_ else None

    def trigger_transition(
        self, trigger: str, *,
        candidate_id: int | None = None,
        round_id: UUID | None = None,
    ) -> EvaluationResponse:
        t = TRANSITIONS.get(trigger)
        if not t:
            raise ValueError(f"Unknown transition: {trigger}")

        if candidate_id is None:
            if round_id is not None:
                candidate_id = self._resolve_round_candidate(round_id)
            if candidate_id is None:
                raise ValueError(f"Cannot resolve candidate_id for trigger={trigger}, round_id={round_id}")

        if t.set_final_verdict is not None:
            existing = self.repo.get_final_verdict(candidate_id)
            if existing and existing != "ON_HOLD":
                raise CandidateFinalizedException(candidate_id, existing)

        candidate = self.repo.apply_transition(candidate_id, final_verdict=t.set_final_verdict, status=t.set_status)
        if not candidate:
            existing = self.repo.get_by_candidate_id(candidate_id)
            if not existing:
                raise ApplicationNotFoundException(candidate_id)
            raise CandidateFinalizedException(candidate_id, existing.final_verdict)

        logger.info(
            "Transition applied: candidate_id=%s | trigger=%s | final_verdict=%s | status=%s",
            candidate_id, trigger, t.set_final_verdict, t.set_status,
        )
        if t.set_final_verdict in ("SELECTED", "REJECTED", "ON_HOLD"):
            _verdict_event_name = {
                "SELECTED": "Candidate Selected",
                "REJECTED": "Candidate Rejected",
                "ON_HOLD": "Candidate Put On Hold",
            }[t.set_final_verdict]
            _verdict_state_code = {
                "SELECTED": "FINAL_SELECTED",
                "REJECTED": "FINAL_REJECTED",
                "ON_HOLD": "FINAL_ON_HOLD",
            }[t.set_final_verdict]
            EventService(self.db).create_event(EventCreate(
                entity_type="CANDIDATE",
                entity_id=str(candidate_id),
                event_name=_verdict_event_name,
                state_code=_verdict_state_code,
                actor_type="HR",
                candidate_id=candidate_id,
                event_metadata={"final_verdict": t.set_final_verdict},
            ))
            if candidate.external_job_id:
                jd_uuid = self.repo.resolve_hiring_request_id(candidate.external_job_id)
                if jd_uuid:
                    from app.modules.notifications.notification_model import NotificationType
                    from app.modules.notifications.notification_service import NotificationService

                    _verdict_display = t.set_final_verdict.replace("_", " ").title()
                    _verdict_lower = t.set_final_verdict.replace("_", " ").lower()
                    NotificationService(self.db).notify_job_team_and_admins(
                        jd_uuid,
                        notification_type=NotificationType.FINAL_VERDICT.value,
                        title=f"Candidate {_verdict_display}",
                        body=f"{candidate.candidate_name or f'Candidate #{candidate_id}'} was {_verdict_lower}.",
                        action_url=f"/hiring-requests/{jd_uuid}/candidates/{candidate_id}",
                        action_label="View candidate",
                        candidate_id=candidate_id,
                        dedupe_key=f"FINAL_VERDICT-{candidate_id}",
                    )
            self._cancel_active_interviews(candidate_id)
        return EvaluationResponse.model_validate(candidate)

    def _cancel_active_interviews(self, candidate_id: int) -> None:
        from app.modules.interviews.interview_helpers import get_calendar_service
        from app.modules.interviews.models.interview import Interview
        from app.modules.rounds.round_model import Round
        from app.modules.slots.slot_model import Slot, SlotStatus
        from app.scheduler import get_scheduler

        active_statuses = (InterviewStatus.SCHEDULED.value, InterviewStatus.RESCHEDULED.value)
        interviews = (
            self.db.query(Interview)
            .join(Round, Round.id == Interview.round_id)
            .filter(Round.candidate_id == candidate_id, Interview.status.in_(active_statuses))
            .all()
        )
        if not interviews:
            return

        logger.info("Cancelling %d active interview(s) for candidate_id=%s", len(interviews), candidate_id)
        for interview in interviews:
            if interview.event_id:
                try:
                    get_calendar_service().cancel_event(event_id=interview.event_id)
                except Exception as exc:
                    logger.warning("Calendar cancel failed: interview_id=%s | %s", interview.id, exc)
            if interview.slot_id:
                self.db.query(Slot).filter(Slot.id == interview.slot_id).update({"status": SlotStatus.AVAILABLE.value})
            interview.status = InterviewStatus.CANCELLED.value
            try:
                job_id = f"interview_fallback_{interview.id}"
                get_scheduler().remove_job(job_id)
                logger.info("Fallback job removed via final verdict | job_id=%s", job_id)
            except Exception:
                logger.debug("No fallback job to remove via final verdict | interview_id=%s", interview.id)
            EventService(self.db).create_event(EventCreate(
                entity_type="CANDIDATE",
                entity_id=str(candidate_id),
                event_name="Interview Cancelled",
                state_code="INTERVIEW_CANCELLED",
                actor_type="SYSTEM",
                candidate_id=candidate_id,
                event_metadata={"interview_id": str(interview.id), "reason": "candidate_finalised"},
            ))
        self.db.commit()

    def handle_hr_verdict(self, round_id: UUID, verdict: str | None) -> None:
        TRIGGER_MAP: dict[str, str] = {
            "shortlisted": "hr.shortlisted",
            "rejected": "hr.rejected",
        }
        trigger = TRIGGER_MAP.get(verdict) if verdict else None
        if not trigger:
            return
        try:
            self.trigger_transition(trigger, round_id=round_id)
        except Exception as exc:
            logger.warning("Failed HR transition: trigger=%s | round_id=%s | %s", trigger, round_id, exc)

    def set_final_verdict(self, candidate_id: int, verdict: str) -> EvaluationResponse:
        return self.trigger_transition(f"final.selection.{verdict}", candidate_id=candidate_id)

    def update_candidate_status(self, candidate_id: int, new_status: str) -> EvaluationResponse:
        # Capture from-state before the mutation so the event metadata can
        # describe the transition rather than just the destination.
        existing = self.repo.get_by_candidate_id(candidate_id)
        prev_status = existing.status if existing else None

        candidate = self.repo.update_status(candidate_id, new_status)
        if not candidate:
            if not existing:
                raise ApplicationNotFoundException(candidate_id)
            raise CandidateFinalizedException(candidate_id, existing.final_verdict)
        self.db.commit()
        self.db.refresh(candidate)
        logger.info("Candidate status updated: candidate_id=%s | status=%s", candidate_id, new_status)

        if prev_status != new_status:
            EventService(self.db).create_event(EventCreate(
                entity_type="CANDIDATE",
                entity_id=str(candidate_id),
                event_name="Candidate Status Changed",
                state_code="STATUS_CHANGED",
                actor_type="HR",
                candidate_id=candidate_id,
                event_metadata={"from_status": prev_status, "to_status": new_status},
            ))
        return EvaluationResponse.model_validate(candidate)

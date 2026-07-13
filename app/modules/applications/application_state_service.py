from uuid import UUID

from sqlalchemy.orm import Session

from app.common.exceptions.application_exception import (
    ApplicationNotFoundException,
    CandidateFinalizedException,
)
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

    def trigger_transition(self, trigger: str, *, candidate_id: int | None = None, round_id: UUID | None = None) -> EvaluationResponse:
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
            if existing:
                raise CandidateFinalizedException(candidate_id, existing)

        candidate = self.repo.apply_transition(candidate_id, final_verdict=t.set_final_verdict, status=t.set_status)
        if not candidate:
            existing = self.repo.get_by_candidate_id(candidate_id)
            if not existing:
                raise ApplicationNotFoundException(candidate_id)
            raise CandidateFinalizedException(candidate_id, existing.final_verdict)

        logger.info("Transition applied: candidate_id=%s | trigger=%s | final_verdict=%s | status=%s", candidate_id, trigger, t.set_final_verdict, t.set_status)
        if t.set_final_verdict in ("SELECTED", "REJECTED"):
            EventService(self.db).create_event(EventCreate(
                entity_type="CANDIDATE",
                entity_id=str(candidate_id),
                event_name="Candidate Selected" if t.set_final_verdict == "SELECTED" else "Candidate Rejected",
                state_code="FINAL_SELECTED" if t.set_final_verdict == "SELECTED" else "FINAL_REJECTED",
                actor_type="HR",
                candidate_id=candidate_id,
                event_metadata={"final_verdict": t.set_final_verdict},
            ))
        return EvaluationResponse.model_validate(candidate)

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
        candidate = self.repo.update_status(candidate_id, new_status)
        if not candidate:
            existing = self.repo.get_by_candidate_id(candidate_id)
            if not existing:
                raise ApplicationNotFoundException(candidate_id)
            raise CandidateFinalizedException(candidate_id, existing.final_verdict)
        self.db.commit()
        self.db.refresh(candidate)
        logger.info("Candidate status updated: candidate_id=%s | status=%s", candidate_id, new_status)
        return EvaluationResponse.model_validate(candidate)

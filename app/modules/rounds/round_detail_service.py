from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.constants import InterviewStatus
from app.core.logger import get_logger
from app.modules.evaluations.evaluation_model import Candidate
from app.modules.hiring_requests.hiring_request_model import HiringRequest
from app.modules.interviews.interview_repository import InterviewRepository
from app.modules.interviews.models.interview import Interview
from app.modules.interviews.models.round_interviewer import RoundInterviewer
from app.modules.reviews.review_service import ReviewService
from app.modules.rounds.round_model import Round
from app.modules.rounds.round_repository import RoundRepositoryProtocol
from app.modules.rounds.round_schema import RoundDetailResponse, ReviewEntity, RatingItem
from app.modules.slots.slot_model import Slot
from app.modules.slots.slot_presenter import format_slot_label_ist, to_ist
from app.modules.users.user_model import User

logger = get_logger(__name__)

_NON_RATING_NUMERIC_KEYS: set[str] = {"average_rating"}
_VERDICT_NORMALIZE: dict[str, str] = {"reject": "rejected"}

_ROUND_VERDICT_DISPLAY: dict[str, str] = {
    "selected": "Selected",
    "rejected": "Rejected",
    "hold": "On Hold",
    "advance": "Advanced",
    "shortlisted": "Shortlisted",
}

_AI_VERDICT_DISPLAY: dict[str, str] = {
    "shortlisted": "Shortlisted",
    "rejected": "Rejected",
    "selected": "Selected",
}


class RoundDetailService:
    def __init__(self, db: Session, repo: RoundRepositoryProtocol):
        self.db = db
        self.repository = repo

    def get_round_detail(self, round_id: UUID) -> RoundDetailResponse | None:
        logger.info("Fetching round detail for round_id=%s", round_id)

        round_obj = self.repository.get_by_id(round_id)
        if not round_obj:
            logger.warning("Round not found: round_id=%s", round_id)
            return None

        review_svc = ReviewService(self.db)
        reviews = review_svc.get_reviews_by_round(str(round_id))

        candidate = (
            self.db.query(Candidate).filter(Candidate.id == round_obj.candidate_id).first()
            if round_obj.candidate_id else None
        )
        slot = (
            self.db.query(Slot).filter(Slot.id == round_obj.slot_id).first()
            if round_obj.slot_id else None
        )
        jd = (
            self.db.query(HiringRequest).filter(HiringRequest.id == round_obj.jd_id).first()
            if round_obj.jd_id else None
        )

        interview = InterviewRepository(self.db).get_by_round_id(round_id)

        interviewer: str | None = None
        if slot:
            user = self.db.query(User).filter(User.id == slot.employee_id).first()
            interviewer = user.name if user else None

        interviewer_names = self._interviewer_names_for_round(round_id)
        if not interviewer_names and interviewer:
            interviewer_names = [interviewer]

        entities: list[ReviewEntity] = []
        for r in reviews:
            rv: dict = r.reviews or {}
            ratings: list[RatingItem] = []
            rest: dict[str, object] = {}
            for k, v in rv.items():
                if isinstance(v, (int, float)) and k not in _NON_RATING_NUMERIC_KEYS:
                    max_score = 100 if k == "fitscore" else 5
                    ratings.append(RatingItem(
                        label=k,
                        score=float(v),
                        max_score=max_score,
                        entity_type=r.entity_type.lower(),
                    ))
                else:
                    rest[k] = v

            verdict = _VERDICT_NORMALIZE.get(r.verdict, r.verdict) if r.verdict else None
            entity = ReviewEntity(
                entity_type=r.entity_type.lower(),
                verdict=verdict,
                ratings=ratings,
            )
            for k, v in rest.items():
                setattr(entity, k, v)
            entities.append(entity)

        return RoundDetailResponse(
            id=round_obj.id,
            round=round_obj.name,
            duration=self._compute_duration(slot),
            interview_type=None,
            occurred_on=self._format_datetime_ist(round_obj.created_at),
            slot=self._format_slot_ist(slot),
            status=self._resolve_display_status(round_obj, interview, slot, entities),
            candidate=candidate.candidate_name if candidate else None,
            role=jd.title if jd else None,
            jd_label=jd.description if jd else None,
            interviewer=interviewer,
            has_interview=interview is not None,
            interviewers=interviewer_names,
            review_form_status=self._review_form_status_for_round(round_id),
            reviews=entities,
        )

    def _interviewer_names_for_round(self, round_id: UUID) -> list[str]:
        users = (
            self.db.query(User)
            .join(RoundInterviewer, RoundInterviewer.employee_id == User.id)
            .filter(RoundInterviewer.round_id == round_id)
            .all()
        )
        return [u.name for u in users if u.name]

    def _review_form_status_for_round(self, round_id: UUID) -> str | None:
        from sqlalchemy import text

        rows = self.db.execute(
            text(
                "SELECT status FROM forms WHERE round_id = :round_id AND type = 'REVIEW'"
            ),
            {"round_id": str(round_id)},
        ).fetchall()
        statuses = {row[0] for row in rows}
        if not statuses:
            return None
        if "SUBMITTED" in statuses:
            return "received"
        if "SENT" in statuses:
            return "awaiting"
        if "EXPIRED" in statuses:
            return "expired"
        return None

    @staticmethod
    def _compute_duration(slot: Slot | None) -> str | None:
        if not slot:
            return None
        delta = slot.end_at - slot.start_at
        total_minutes = int(delta.total_seconds() // 60)
        if total_minutes < 60:
            return f"{total_minutes} mins"
        hours = total_minutes // 60
        mins = total_minutes % 60
        return f"{hours}h {mins}m" if mins else f"{hours}h"

    @staticmethod
    def _format_datetime_ist(dt: datetime | None) -> str | None:
        if not dt:
            return None
        local = to_ist(dt)
        return local.strftime("%B %d, %Y • %I:%M %p").replace(" 0", " ")

    @staticmethod
    def _format_slot_ist(slot: Slot | None) -> str | None:
        if not slot:
            return None
        return format_slot_label_ist(slot.start_at, slot.end_at).replace(" - ", " – ").replace(" 0", " ")

    @staticmethod
    def _resolve_display_status(
        round_obj: Round,
        interview: Interview | None,
        slot: Slot | None,
        entities: list[ReviewEntity],
    ) -> str:
        if interview:
            return RoundDetailService._status_from_interview(interview, slot)

        if round_obj.round_verdict:
            key = round_obj.round_verdict.lower()
            return _ROUND_VERDICT_DISPLAY.get(key, round_obj.round_verdict.capitalize())

        ai_verdict = next(
            (e.verdict for e in entities if e.entity_type == "ai" and e.verdict),
            None,
        )
        if ai_verdict:
            key = ai_verdict.lower()
            return _AI_VERDICT_DISPLAY.get(key, ai_verdict.capitalize())

        if entities:
            return "Completed"
        return "Pending"

    @staticmethod
    def _status_from_interview(interview: Interview, slot: Slot | None) -> str:
        status = (interview.status or "").upper()
        if status == InterviewStatus.COMPLETED.value:
            return "Completed"
        if status == InterviewStatus.CANCELLED.value:
            return "Cancelled"

        if status in (InterviewStatus.SCHEDULED.value, InterviewStatus.RESCHEDULED.value):
            start = slot.start_at if slot else None
            if start is not None:
                start_utc = start if start.tzinfo else start.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                if start_utc <= now:
                    return "In progress"
            return "Scheduled"

        return status.capitalize() if status else "Pending"

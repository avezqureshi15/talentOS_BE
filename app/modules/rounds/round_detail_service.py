from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.modules.evaluations.evaluation_model import Candidate
from app.modules.hiring_requests.hiring_request_model import HiringRequest
from app.modules.reviews.review_service import ReviewService
from app.modules.rounds.round_model import Round
from app.modules.rounds.round_repository import RoundRepositoryProtocol
from app.modules.rounds.round_schema import RoundDetailResponse, ReviewEntity, RatingItem
from app.modules.slots.slot_model import Slot
from app.modules.users.user_model import User

logger = get_logger(__name__)

_NON_RATING_NUMERIC_KEYS: set[str] = {"average_rating"}
_VERDICT_NORMALIZE: dict[str, str] = {"reject": "rejected"}


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

        interviewer: str | None = None
        if slot:
            # slot.employee_id now points at employees.id; resolve to a User
            # via the back-pointer to keep the auth-side name/label consistent.
            user = (
                self.db.query(User)
                .filter(User.employee_id == slot.employee_id)
                .first()
            )
            interviewer = user.name if user else None

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

            # Extract per-question scores from sections/phases when no top-level numeric ratings
            if not ratings and r.entity_type.lower() == "interviewer":
                groups = rv.get("sections") or rv.get("phases") or []
                for group in groups:
                    group_name = (group.get("section") or group.get("phase") or "Overall").strip()
                    for answer in group.get("answers", []):
                        if isinstance(answer.get("score"), (int, float)):
                            q_label = str(answer.get("question", "")).strip()[:60]
                            ratings.append(RatingItem(
                                label=f"{group_name}: {q_label}" if q_label else group_name,
                                score=float(answer["score"]),
                                max_score=5.0,
                                entity_type="interviewer",
                            ))

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
            round_type=round_obj.round_type,
            round=round_obj.name,
            duration=self._compute_duration(slot),
            interview_type=round_obj.name,
            occurred_on=self._format_datetime(round_obj.created_at),
            slot=self._format_slot_time(slot),
            status=self._resolve_status(slot, reviews),
            candidate=candidate.candidate_name if candidate else None,
            candidate_id=round_obj.candidate_id,
            role=jd.title if jd else None,
            jd_label=jd.description if jd else None,
            interviewer=interviewer,
            reviews=entities,
        )

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
    def _format_datetime(dt: datetime | None) -> str | None:
        if not dt:
            return None
        return dt.strftime("%B %d, %Y • %I:%M %p").replace(" 0", " ")

    @staticmethod
    def _format_slot_time(slot: Slot | None) -> str | None:
        if not slot:
            return None
        fmt = "%I:%M %p"
        return f"{slot.start_at.strftime(fmt)} – {slot.end_at.strftime(fmt)}".replace(" 0", " ")

    @staticmethod
    def _resolve_status(slot: Slot | None, reviews) -> str:
        if slot:
            return slot.status.capitalize()

        # AI screening/interview rounds: derive status from the reviews JSONB
        # (no rounds.status column exists; the webhook/pull persist writes
        # status / call_status into the ai_* review payloads).
        if reviews:
            for r in reviews:
                rv: dict = r.reviews or {}
                entity = (r.entity_type or "").lower()
                if entity == "ai_screening":
                    call_status = (rv.get("call_status") or rv.get("status") or "").lower()
                    if call_status in ("queued", "pending", "initiated", "in_progress"):
                        return "In Progress"
                    if call_status == "completed":
                        return "Completed"
                    if call_status == "failed":
                        return "Failed"
                elif entity == "ai_interview":
                    status = (rv.get("status") or "").lower()
                    if status in ("pending", "in_progress"):
                        return "In Progress"
                    if status in ("completed", "assessed"):
                        return "Completed"
                    if status == "assessment_failed":
                        return "Failed"
                    if status == "expired":
                        return "Expired"
            return "Completed"

        return "Pending"

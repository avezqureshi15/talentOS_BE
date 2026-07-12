from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.modules.evaluations.evaluation_model import Candidate
from app.modules.hiring_requests.hiring_request_model import HiringRequest
from app.modules.reviews.review_service import ReviewService
from app.modules.rounds.round_model import Round
from app.modules.rounds.round_repository import RoundRepositoryProtocol
from app.modules.rounds.round_schema import RoundDetailResponse
from app.modules.slots.slot_model import Slot
from app.modules.users.user_model import User

logger = get_logger(__name__)

LIFTED_KEYS = {"summary_md", "summary", "remarks", "skills", "notes", "rejected_status", "rejected_reason", "YOE", "CTC", "LOCATION", "NOTICE_PERIOD", "EXPERIENCE"}


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

        candidate: Candidate | None = (
            self.db.query(Candidate).filter(Candidate.id == round_obj.candidate_id).first()
            if round_obj.candidate_id else None
        )
        slot: Slot | None = (
            self.db.query(Slot).filter(Slot.id == round_obj.slot_id).first()
            if round_obj.slot_id else None
        )
        jd: HiringRequest | None = (
            self.db.query(HiringRequest).filter(HiringRequest.id == round_obj.jd_id).first()
            if round_obj.jd_id else None
        )

        interviewer: str | None = None
        if slot:
            user = self.db.query(User).filter(User.id == slot.employee_id).first()
            interviewer = user.name if user else None

        VERDICT_NORMALIZE: dict[str, str] = {"reject": "rejected"}
        decisions: dict[str, str] = {}
        for r in reviews:
            key = f"{r.entity_type.lower()}_decision"
            raw = r.verdict or "pending"
            decisions[key] = VERDICT_NORMALIZE.get(raw, raw)

        ai_summary: str | None = None
        notes: str | None = None
        remarks_hr: str | None = None
        remarks_interviewer: str | None = None
        all_skills: list[str] = []
        rating_items: list[dict] = []
        seen_rating_labels: set[str] = set()
        strong_matches: list[str] = []
        gaps_and_concerns: list[str] = []
        rejected_status: list[str] = []
        rejected_reason: str | None = None

        for r in reviews:
            rv: dict = r.reviews or {}
            if r.entity_type.lower() == "ai":
                ai_summary = rv.get("summary") or rv.get("summary_md")
                strong_matches = rv.get("strong_matches", [])
                gaps_and_concerns = rv.get("gaps_and_concerns", [])
                rejected_status = rv.get("rejected_status", [])
                rejected_reason = rv.get("rejected_reason")
            if r.entity_type.lower() == "hr":
                remarks_hr = rv.get("remarks")
            if r.entity_type.lower() == "interviewer":
                remarks_interviewer = rv.get("remarks")
            if rv.get("notes"):
                notes = rv.get("notes")
            skills_raw = rv.get("skills", [])
            if isinstance(skills_raw, list):
                all_skills.extend(skills_raw)
            for k, v in rv.items():
                if k in LIFTED_KEYS or k in seen_rating_labels:
                    continue
                max_score = 100 if k == "fitscore" else 5
                rating_items.append({
                    "label": k,
                    "score": float(v) if isinstance(v, (int, float)) else 0,
                    "max_score": max_score,
                    "entity_type": r.entity_type.lower(),
                })
                seen_rating_labels.add(k)

        seen: set[str] = set()
        unique_skills: list[str] = []
        for s in all_skills:
            if s not in seen:
                seen.add(s)
                unique_skills.append(s)

        return RoundDetailResponse(
            id=round_obj.id,
            round=round_obj.name,
            duration=self._compute_duration(slot),
            interview_type=round_obj.name,
            occurred_on=self._format_datetime(round_obj.created_at),
            slot=self._format_slot_time(slot),
            status=self._resolve_status(slot, bool(reviews)),
            candidate=candidate.candidate_name if candidate else None,
            role=jd.title if jd else None,
            jd_label=jd.description if jd else None,
            interviewer=interviewer,
            decisions=decisions,
            ai_summary=ai_summary,
            strong_matches=strong_matches,
            gaps_and_concerns=gaps_and_concerns,
            ratings=rating_items,
            skills=unique_skills,
            notes=notes,
            remarks_hr=remarks_hr,
            remarks_interviewer=remarks_interviewer,
            rejected_status=rejected_status,
            rejected_reason=rejected_reason,
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
    def _resolve_status(slot: Slot | None, has_reviews: bool) -> str:
        if slot:
            return slot.status.capitalize()
        return "Completed" if has_reviews else "Pending"

import uuid

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.constants import EvaluationStatus, PipelineStage
from app.core.logger import get_logger
from app.modules.evaluations.evaluation_model import Candidate
from app.modules.reviews.review_model import Review
from app.modules.reviews.review_repository import ReviewRepository, ReviewRepositoryProtocol
from app.modules.events.event_schema import EventCreate
from app.modules.events.event_service import EventService
from app.modules.reviews.review_schema import (
    InterviewerReviewsPayload,
    ReviewCreate,
    ReviewResponse,
    ReviewUpdateByRound,
)

logger = get_logger(__name__)

_INTERVIEWER_ENTITY = "interviewer"


class ReviewService:
    def __init__(self, db: Session, repo: ReviewRepositoryProtocol | None = None):
        self.db = db
        self.repository = repo or ReviewRepository(db)

    def create_review(self, data: ReviewCreate) -> ReviewResponse:
        logger.info("Creating review: round_id=%s | entity_type=%s", data.round_id, data.entity_type)

        review = Review(
            round_id=data.round_id,
            entity_type=data.entity_type,
            reviews=data.reviews,
            verdict=data.verdict,
        )

        self.repository.create(review)
        self.db.commit()
        self.db.refresh(review)

        return ReviewResponse.model_validate(review)

    def _update_round_verdict(self, round_id: uuid.UUID) -> None:
        from app.modules.rounds.round_model import Round
        reviews = self.repository.get_by_round(str(round_id))
        _PRIORITY: dict[str, int] = {"hr": 3, "interviewer": 2, "ai": 1}
        best, best_p = None, -1
        for r in reviews:
            p = _PRIORITY.get(r.entity_type.lower(), 0)
            if p > best_p:
                best, best_p = r.verdict, p
        _VERDICT_MAP: dict[str, str] = {
            "shortlisted": "selected", "selected": "selected",
            "rejected": "rejected", "advance": "advance", "hold": "hold",
        }
        mapped = _VERDICT_MAP.get(best) if best else None
        round_obj = self.db.query(Round).filter(Round.id == round_id).first()
        if round_obj and round_obj.round_verdict != mapped:
            round_obj.round_verdict = mapped
            self.db.flush()
            if round_obj.candidate_id:
                EventService(self.db).create_event(EventCreate(
                    entity_type="CANDIDATE",
                    entity_id=str(round_obj.candidate_id),
                    event_name="Round Verdict Updated",
                    state_code="ROUND_VERDICT_UPDATED",
                    actor_type="SYSTEM",
                    candidate_id=round_obj.candidate_id,
                    event_metadata={"round_id": str(round_id), "round_verdict": mapped, "triggered_by": None},
                ))

    def get_reviews_by_round(self, round_id: str) -> list[ReviewResponse]:
        reviews = self.repository.get_by_round(round_id)
        return [ReviewResponse.model_validate(r) for r in reviews]

    @staticmethod
    def _normalize_interviewer_reviews(reviews: dict) -> dict:
        try:
            payload = InterviewerReviewsPayload.model_validate(reviews)
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=exc.errors(),
            ) from exc

        scores = [answer.score for phase in payload.phases for answer in phase.answers]
        if not scores:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Interviewer review must include at least one scored answer",
            )
        payload.average_rating = round(sum(scores) / len(scores), 1)
        return payload.model_dump()

    def upsert_review(self, round_id: uuid.UUID, data: ReviewUpdateByRound) -> ReviewResponse:
        reviews_payload = data.reviews
        if data.entity_type.lower() == _INTERVIEWER_ENTITY:
            reviews_payload = self._normalize_interviewer_reviews(data.reviews)

        review = self.repository.get_by_round_and_entity(round_id, data.entity_type)
        if review:
            logger.info("Updating review: id=%s | round_id=%s", review.id, round_id)
            review.reviews = reviews_payload
            review.verdict = data.verdict
            self.repository.update(review)
        else:
            logger.info("Creating review: round_id=%s | entity_type=%s", round_id, data.entity_type)
            review = Review(
                round_id=round_id,
                entity_type=data.entity_type,
                reviews=reviews_payload,
                verdict=data.verdict,
            )
            self.repository.create(review)
        self.db.commit()
        self.db.refresh(review)
        self._update_round_verdict(round_id)
        if data.entity_type == "interviewer":
            from app.modules.rounds.round_model import Round as _Round
            round_obj = self.db.query(_Round).filter(_Round.id == round_id).first()
            if round_obj and round_obj.candidate_id:
                EventService(self.db).create_event(EventCreate(
                    entity_type="CANDIDATE",
                    entity_id=str(round_obj.candidate_id),
                    event_name="Interviewer Review Submitted",
                    state_code="INTERVIEWER_REVIEWED",
                    actor_type="INTERVIEWER",
                    candidate_id=round_obj.candidate_id,
                    event_metadata={"round_id": str(round_id), "verdict": data.verdict},
                ))
                self.db.query(Candidate).filter(Candidate.id == round_obj.candidate_id).update(
                    {"status": EvaluationStatus.UNDER_EVALUATION.value}
                )
                self.db.flush()
                EventService(self.db).create_event(EventCreate(
                    entity_type="CANDIDATE",
                    entity_id=str(round_obj.candidate_id),
                    event_name="Candidate Under Evaluation",
                    state_code="UNDER_EVALUATION",
                    actor_type="INTERVIEWER",
                    candidate_id=round_obj.candidate_id,
                    event_metadata={
                        "round_id": str(round_id),
                        "verdict": data.verdict,
                        "triggered_by": "interviewer_review",
                    },
                ))
        return ReviewResponse.model_validate(review)

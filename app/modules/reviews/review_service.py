import uuid

from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.modules.reviews.review_model import Review
from app.modules.reviews.review_repository import ReviewRepository, ReviewRepositoryProtocol
from app.modules.reviews.review_schema import ReviewCreate, ReviewResponse, ReviewUpdateByRound

logger = get_logger(__name__)


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

    def get_reviews_by_round(self, round_id: str) -> list[ReviewResponse]:
        reviews = self.repository.get_by_round(round_id)
        return [ReviewResponse.model_validate(r) for r in reviews]

    def upsert_review(self, round_id: uuid.UUID, data: ReviewUpdateByRound) -> ReviewResponse:
        review = self.repository.get_by_round_and_entity(round_id, data.entity_type)
        if review:
            logger.info("Updating review: id=%s | round_id=%s", review.id, round_id)
            review.reviews = data.reviews
            review.verdict = data.verdict
            self.repository.update(review)
        else:
            logger.info("Creating review: round_id=%s | entity_type=%s", round_id, data.entity_type)
            review = Review(
                round_id=round_id,
                entity_type=data.entity_type,
                reviews=data.reviews,
                verdict=data.verdict,
            )
            self.repository.create(review)
        self.db.commit()
        self.db.refresh(review)
        return ReviewResponse.model_validate(review)

from typing import Protocol

from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.modules.reviews.review_model import Review

logger = get_logger(__name__)


class ReviewRepositoryProtocol(Protocol):
    def create(self, review: Review) -> Review: ...
    def get_by_round(self, round_id: str) -> list[Review]: ...


class ReviewRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, review: Review) -> Review:
        logger.info("Persisting review: round_id=%s | entity_type=%s", review.round_id, review.entity_type)
        self.db.add(review)
        self.db.flush()
        return review

    def get_by_round(self, round_id: str) -> list[Review]:
        return (
            self.db.query(Review)
            .filter(Review.round_id == round_id)
            .order_by(Review.created_at)
            .all()
        )

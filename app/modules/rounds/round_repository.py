from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.modules.evaluations.evaluation_model import Candidate
from app.modules.rounds.round_model import Round

logger = get_logger(__name__)


class RoundRepositoryProtocol(Protocol):
    def create(self, round_obj: Round) -> Round: ...
    def get_by_candidate(self, candidate_id: int) -> list[Round]: ...
    def get_by_external_application(self, application_id: str) -> list[Round]: ...


class RoundRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, round_obj: Round) -> Round:
        logger.info("Persisting round: name=%s", round_obj.name)
        self.db.add(round_obj)
        self.db.flush()
        return round_obj

    def get_by_candidate(self, candidate_id: int) -> list[Round]:
        return (
            self.db.query(Round)
            .filter(Round.candidate_id == candidate_id)
            .order_by(Round.created_at)
            .all()
        )

    def get_by_external_application(self, application_id: str) -> list[Round]:
        stmt = (
            select(Round)
            .join(Candidate, Round.candidate_id == Candidate.id)
            .where(Candidate.external_application_id == application_id)
            .order_by(Round.created_at)
        )
        return list(self.db.execute(stmt).scalars().all())

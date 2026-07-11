from typing import Protocol

from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.modules.rounds.round_model import Round

logger = get_logger(__name__)


class RoundRepositoryProtocol(Protocol):
    def create(self, round_obj: Round) -> Round: ...


class RoundRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, round_obj: Round) -> Round:
        logger.info("Persisting round: name=%s", round_obj.name)
        self.db.add(round_obj)
        self.db.flush()
        return round_obj

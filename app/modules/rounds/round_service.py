from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.modules.rounds.round_model import Round
from app.modules.rounds.round_repository import RoundRepository, RoundRepositoryProtocol
from app.modules.rounds.round_schema import RoundCreate, RoundResponse

logger = get_logger(__name__)


class RoundService:
    def __init__(self, db: Session, repo: RoundRepositoryProtocol | None = None):
        self.db = db
        self.repository = repo or RoundRepository(db)

    def create_round(self, data: RoundCreate) -> RoundResponse:
        logger.info("Creating round: name=%s | candidate_id=%s", data.name, data.candidate_id)

        round_obj = Round(
            name=data.name,
            candidate_id=data.candidate_id,
            slot_id=data.slot_id,
            jd_id=data.jd_id,
        )

        self.repository.create(round_obj)
        self.db.commit()
        self.db.refresh(round_obj)

        return RoundResponse.model_validate(round_obj)

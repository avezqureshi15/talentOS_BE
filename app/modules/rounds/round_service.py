from uuid import UUID

from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.modules.rounds.round_detail_service import RoundDetailService
from app.modules.rounds.round_model import Round
from app.modules.rounds.round_repository import RoundRepository, RoundRepositoryProtocol
from app.modules.rounds.round_schema import RoundCreate, RoundDetailResponse, RoundResponse

logger = get_logger(__name__)


class RoundService:
    def __init__(self, db: Session, repo: RoundRepositoryProtocol | None = None):
        self.db = db
        self.repository = repo or RoundRepository(db)
        self._detail_svc = RoundDetailService(db, self.repository)

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

    def get_rounds_by_candidate(self, candidate_id: int) -> list[RoundResponse]:
        logger.info("Fetching rounds for candidate_id=%s", candidate_id)
        rounds = self.repository.get_by_candidate(candidate_id)
        return [RoundResponse.model_validate(r) for r in rounds]

    def get_rounds_by_external_application(self, application_id: str) -> list[RoundResponse]:
        logger.info("Fetching rounds for external_application_id=%s", application_id)
        rounds = self.repository.get_by_external_application(application_id)
        return [RoundResponse.model_validate(r) for r in rounds]

    def get_round_detail(self, round_id: UUID) -> RoundDetailResponse | None:
        return self._detail_svc.get_round_detail(round_id)

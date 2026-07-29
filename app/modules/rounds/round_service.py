from datetime import datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.modules.evaluations.evaluation_model import Candidate
from app.modules.rounds.round_detail_service import RoundDetailService
from app.modules.rounds.round_model import Round
from app.modules.rounds.round_repository import RoundRepository, RoundRepositoryProtocol
from app.modules.rounds.round_schema import (
    PaginatedRoundResponse,
    RoundCreate,
    RoundDetailResponse,
    RoundListItem,
    RoundResponse,
)

logger = get_logger(__name__)


class RoundService:
    def __init__(self, db: Session, repo: RoundRepositoryProtocol | None = None):
        self.db = db
        self.repository = repo or RoundRepository(db)
        self._detail_svc = RoundDetailService(db, self.repository)

    def create_round(self, data: RoundCreate) -> RoundResponse:
        logger.info("Creating round: name=%s | candidate_id=%s", data.name, data.candidate_id)
        if data.candidate_id:
            candidate = self.db.query(Candidate).filter(Candidate.id == data.candidate_id).first()
            if candidate and candidate.current_round_id:
                current_round = self.db.query(Round).filter(Round.id == candidate.current_round_id).first()
                if current_round and current_round.round_verdict is None:
                    raise HTTPException(
                        status_code=400,
                        detail="Current round verdict must be filled before scheduling a new round",
                    )
        def _parse_date(val: str | None):
            if not val: return None
            try: return datetime.strptime(val, "%Y-%m-%d").date()
            except ValueError: return None

        def _parse_time(val: str | None):
            if not val: return None
            try: return datetime.strptime(val, "%H:%M").time()
            except ValueError: return None

        round_obj = Round(
            name=data.name,
            round_type=data.round_type,
            candidate_id=data.candidate_id,
            slot_id=data.slot_id,
            jd_id=data.jd_id,
            scheduled_date=_parse_date(data.scheduled_date),
            scheduled_time=_parse_time(data.scheduled_time),
            scheduled_end_date=_parse_date(data.scheduled_end_date),
            scheduled_end_time=_parse_time(data.scheduled_end_time),
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

    def get_rounds_paginated(
        self,
        page: int = 1,
        per_page: int = 20,
        search: str | None = None,
        candidate_id: int | None = None,
    ) -> PaginatedRoundResponse:
        rows, total = self.repository.get_all_paginated(
            page=page, per_page=per_page, search=search, candidate_id=candidate_id,
        )
        items = [
            RoundListItem(
                id=str(row.id),
                name=row.name,
                round_verdict=row.round_verdict,
                candidate_name=row.candidate_name,
                candidate_id=str(row.external_application_id) if row.external_application_id else None,
                position_title=row.position_title,
                created_at=row.created_at.isoformat() if row.created_at else None,
            )
            for row in rows
        ]
        return PaginatedRoundResponse(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
            has_more=(page * per_page) < total,
        )

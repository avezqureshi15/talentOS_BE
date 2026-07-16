from typing import Protocol
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.modules.evaluations.evaluation_model import Candidate
from app.modules.hiring_requests.hiring_request_model import HiringRequest
from app.modules.rounds.round_model import Round

logger = get_logger(__name__)


class RoundRepositoryProtocol(Protocol):
    def create(self, round_obj: Round) -> Round: ...
    def get_by_candidate(self, candidate_id: int) -> list[Round]: ...
    def get_by_external_application(self, application_id: str) -> list[Round]: ...
    def get_by_id(self, round_id: UUID) -> Round | None: ...


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

    def get_by_id(self, round_id: UUID) -> Round | None:
        return self.db.query(Round).filter(Round.id == round_id).first()

    def get_all_paginated(
        self,
        page: int = 1,
        per_page: int = 20,
        search: str | None = None,
        candidate_id: int | None = None,
    ) -> tuple[list[tuple], int]:
        query = (
            self.db.query(
                Round.id,
                Round.name,
                Round.round_verdict,
                Round.created_at,
                Round.candidate_id,
                Round.jd_id,
                Candidate.candidate_name,
                Candidate.external_application_id,
                HiringRequest.title.label("position_title"),
            )
            .outerjoin(Candidate, Round.candidate_id == Candidate.id)
            .outerjoin(HiringRequest, Round.jd_id == HiringRequest.id)
        )
        if candidate_id is not None:
            query = query.filter(Round.candidate_id == candidate_id)
        if search:
            pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Round.name.ilike(pattern),
                    Candidate.candidate_name.ilike(pattern),
                    HiringRequest.title.ilike(pattern),
                )
            )
        total = query.count()
        rows = (
            query.order_by(Round.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return rows, total

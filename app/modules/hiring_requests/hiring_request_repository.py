from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import cast, or_, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.core.job_access import scope_job_query
from app.modules.auth.auth_schema import UserInfo
from app.modules.hiring_requests.hiring_request_model import HiringRequest


class HiringRequestRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: dict) -> HiringRequest:
        record = HiringRequest(**data)
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_by_id(self, hiring_request_id: UUID) -> HiringRequest | None:
        return self.db.query(HiringRequest).filter(HiringRequest.id == hiring_request_id).first()

    def resolve_to_external_job_id(self, identifier: UUID) -> HiringRequest | None:
        return self.db.query(HiringRequest).filter(
            (HiringRequest.id == identifier) | (HiringRequest.external_job_id == identifier)
        ).first()

    def get_all(
        self,
        search: str | None = None,
        department: str | None = None,
        location: str | None = None,
        type: str | None = None,
        is_active: bool | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        page: int = 1,
        per_page: int = 10,
        tenant_id: int | None = None,
        user: UserInfo | None = None,
    ) -> tuple[list[HiringRequest], int]:
        query = self.db.query(HiringRequest).filter(HiringRequest.deleted_at.is_(None))

        if user is not None:
            query = scope_job_query(query, user)
        if tenant_id is not None:
            query = query.filter(HiringRequest.tenant_id == tenant_id)

        if search and search.strip():
            term = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    HiringRequest.title.ilike(term),
                    HiringRequest.department.ilike(term),
                    cast(HiringRequest.location, String).ilike(term),
                ),
            )

        if department:
            query = query.filter(HiringRequest.department.ilike(department))

        if location:
            query = query.filter(cast(HiringRequest.location, JSONB).contains([location]))

        if type:
            query = query.filter(HiringRequest.type.ilike(type))

        if is_active is not None:
            query = query.filter(HiringRequest.is_active == is_active)

        if created_from:
            query = query.filter(HiringRequest.created_at >= created_from)

        if created_to:
            query = query.filter(HiringRequest.created_at <= created_to)

        total = query.count()

        query = query.order_by(HiringRequest.created_at.desc())
        query = query.offset((page - 1) * per_page).limit(per_page)

        return query.all(), total

    def update(self, record: HiringRequest, data: dict) -> HiringRequest:
        for key, value in data.items():
            setattr(record, key, value)
        self.db.commit()
        self.db.refresh(record)
        return record

    def count_active(self) -> int:
        return self.db.query(HiringRequest).filter(HiringRequest.deleted_at.is_(None)).count()

    def get_distinct_types(self, user: UserInfo | None = None) -> list[str]:
        query = self.db.query(HiringRequest.type).filter(HiringRequest.deleted_at.is_(None))
        if user is not None:
            query = scope_job_query(query, user)
        return [r[0] for r in query.distinct().order_by(HiringRequest.type.asc()).all()]

    def get_distinct_locations(self, user: UserInfo | None = None) -> list[str]:
        query = self.db.query(HiringRequest.location).filter(HiringRequest.deleted_at.is_(None))
        if user is not None:
            query = scope_job_query(query, user)
        seen: set[str] = set()
        for (raw,) in query.all():
            if isinstance(raw, list):
                for item in raw:
                    if isinstance(item, str) and item.strip():
                        seen.add(item.strip())
            elif isinstance(raw, str) and raw.strip():
                seen.add(raw.strip())
        return sorted(seen)

    def get_distinct_departments(self, user: UserInfo | None = None) -> list[str]:
        query = self.db.query(HiringRequest.department).filter(HiringRequest.deleted_at.is_(None))
        if user is not None:
            query = scope_job_query(query, user)
        return [r[0] for r in query.distinct().order_by(HiringRequest.department.asc()).all()]

    def soft_delete(self, record: HiringRequest) -> HiringRequest:
        record.is_active = False
        record.deleted_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(record)
        return record

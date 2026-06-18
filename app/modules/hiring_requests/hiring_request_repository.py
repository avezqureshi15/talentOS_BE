from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

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

    def get_all(self) -> list[HiringRequest]:
        return (
            self.db.query(HiringRequest)
            .filter(HiringRequest.deleted_at.is_(None))
            .order_by(HiringRequest.created_at.desc())
            .all()
        )

    def update(self, record: HiringRequest, data: dict) -> HiringRequest:
        for key, value in data.items():
            setattr(record, key, value)
        self.db.commit()
        self.db.refresh(record)
        return record

    def soft_delete(self, record: HiringRequest) -> HiringRequest:
        record.is_active = False
        record.deleted_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(record)
        return record

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

    def get_all(self) -> list[HiringRequest]:
        return self.db.query(HiringRequest).order_by(HiringRequest.created_at.desc()).all()

from datetime import datetime
from uuid import UUID

from sqlalchemy import exc as sa_exc
from sqlalchemy.orm import Session

from app.common.exceptions.hiring_request_exception import (
    HiringRequestNotCreatedException,
    HiringRequestNotDeletedException,
    HiringRequestNotFoundException,
    HiringRequestNotUpdatedException,
)
from app.core.logger import get_logger
from app.modules.hiring_requests.hiring_request_repository import HiringRequestRepository
from app.modules.hiring_requests.hiring_request_schema import (
    HiringRequestCreate,
    HiringRequestResponse,
    HiringRequestUpdate,
)
from app.modules.jobs.job_schema import JobCreate, JobUpdate
from app.modules.jobs.job_service import JobService

logger = get_logger(__name__)


class HiringRequestService:
    def __init__(self, db: Session):
        self.repository = HiringRequestRepository(db)
        self.job_service = JobService()

    def create_hiring_request(self, data: HiringRequestCreate) -> dict:
        logger.info("Creating hiring request: title=%s", data.title)
        job_payload = JobCreate(**data.model_dump(exclude={"custom_evaluation_criteria"}))
        job_response = self.job_service.create_job(job_payload)
        supabase_job_id = job_response.get("data", {}).get("id")

        try:
            payload = data.model_dump()
            payload["supabase_job_id"] = supabase_job_id
            local_record = self.repository.create(payload)
        except sa_exc.SQLAlchemyError as exc:
            logger.critical(
                "Hiring request created in Supabase but DB write failed: title=%s | error=%s",
                data.title,
                str(exc),
            )
            raise HiringRequestNotCreatedException(
                "Job listing created in Supabase but failed to save locally"
            ) from exc

        response = HiringRequestResponse.model_validate(local_record).model_dump()
        return {"data": response, "supabase_job": job_response}

    def get_hiring_request_by_id(self, hiring_request_id: UUID) -> dict:
        logger.info("Fetching hiring request: id=%s", hiring_request_id)
        record = self.repository.get_by_id(hiring_request_id)
        if not record:
            raise HiringRequestNotFoundException(str(hiring_request_id))
        response = HiringRequestResponse.model_validate(record).model_dump()
        return {"data": response}

    def get_all_hiring_requests(
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
    ) -> dict:
        logger.info("Fetching hiring requests from local DB search=%s", search)
        records, total = self.repository.get_all(
            search=search,
            department=department,
            location=location,
            type=type,
            is_active=is_active,
            created_from=created_from,
            created_to=created_to,
            page=page,
            per_page=per_page,
        )
        items = [HiringRequestResponse.model_validate(r).model_dump() for r in records]
        return {
            "data": items,
            "count": len(items),
            "page": page,
            "per_page": per_page,
            "total_pages": max(1, (total + per_page - 1) // per_page),
            "total": total,
        }

    def update_hiring_request(self, hiring_request_id: UUID, data: HiringRequestUpdate) -> dict:
        logger.info("Updating hiring request: id=%s", hiring_request_id)
        record = self.repository.get_by_id(hiring_request_id)
        if not record:
            raise HiringRequestNotFoundException(str(hiring_request_id))

        if record.supabase_job_id:
            job_payload = JobUpdate(**data.model_dump(exclude={"custom_evaluation_criteria"}, exclude_unset=True))
            self.job_service.update_job(record.supabase_job_id, job_payload)

        try:
            updated = self.repository.update(record, data.model_dump(exclude_unset=True))
        except sa_exc.SQLAlchemyError as exc:
            logger.critical("Hiring request DB update failed: id=%s | error=%s", hiring_request_id, str(exc))
            raise HiringRequestNotUpdatedException("Failed to save updated hiring request locally") from exc

        response = HiringRequestResponse.model_validate(updated).model_dump()
        return {"data": response}

    def toggle_hiring_request_status(self, hiring_request_id: UUID) -> dict:
        logger.info("Toggling hiring request status: id=%s", hiring_request_id)
        record = self.repository.get_by_id(hiring_request_id)
        if not record:
            raise HiringRequestNotFoundException(str(hiring_request_id))

        new_status = not record.is_active

        if record.supabase_job_id:
            job_payload = JobUpdate(is_active=new_status)
            self.job_service.update_job(record.supabase_job_id, job_payload)

        try:
            updated = self.repository.update(record, {"is_active": new_status})
        except sa_exc.SQLAlchemyError as exc:
            logger.critical("Hiring request DB update failed: id=%s | error=%s", hiring_request_id, str(exc))
            raise HiringRequestNotUpdatedException("Failed to update hiring request status locally") from exc

        response = HiringRequestResponse.model_validate(updated).model_dump()
        return {"data": response}

    def get_types(self) -> dict:
        types = self.repository.get_distinct_types()
        return {"data": types}

    def get_locations(self) -> dict:
        locations = self.repository.get_distinct_locations()
        return {"data": locations}

    def get_departments(self) -> dict:
        departments = self.repository.get_distinct_departments()
        return {"data": departments}

    def delete_hiring_request(self, hiring_request_id: UUID) -> dict:
        logger.info("Deleting hiring request: id=%s", hiring_request_id)
        record = self.repository.get_by_id(hiring_request_id)
        if not record:
            raise HiringRequestNotFoundException(str(hiring_request_id))

        if record.supabase_job_id:
            self.job_service.delete_job(record.supabase_job_id)

        try:
            self.repository.soft_delete(record)
        except sa_exc.SQLAlchemyError as exc:
            logger.critical("Hiring request DB soft delete failed: id=%s | error=%s", hiring_request_id, str(exc))
            raise HiringRequestNotDeletedException("Failed to soft delete hiring request locally") from exc

        logger.info("Hiring request soft deleted: id=%s", hiring_request_id)
        return {"message": "Hiring request deleted successfully"}

from sqlalchemy import exc as sa_exc
from sqlalchemy.orm import Session

from app.common.exceptions.hiring_request_exception import HiringRequestNotCreatedException
from app.core.logger import get_logger
from app.modules.hiring_requests.hiring_request_repository import HiringRequestRepository
from app.modules.hiring_requests.hiring_request_schema import HiringRequestCreate, HiringRequestResponse
from app.modules.jobs.job_schema import JobCreate
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

        try:
            local_record = self.repository.create(data.model_dump())
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

    def get_all_hiring_requests(self) -> dict:
        logger.info("Fetching all hiring requests from local DB")
        records = self.repository.get_all()
        items = [HiringRequestResponse.model_validate(r).model_dump() for r in records]
        return {"data": items, "count": len(items)}

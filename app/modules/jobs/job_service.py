from uuid import UUID

from app.common.clients import SupabaseClient
from app.core.logger import get_logger
from app.modules.jobs.job_schema import JobCreate, JobUpdate

logger = get_logger(__name__)


class JobService:
    def __init__(self):
        self.supabase = SupabaseClient()

    def get_all_jobs(self) -> dict:
        logger.info("Fetching all job listings from Supabase")
        return self.supabase.get_all_jobs()

    def get_job_by_id(self, job_id: UUID) -> dict:
        logger.info("Fetching job listing: id=%s", job_id)
        return self.supabase.get_job_by_id(job_id)

    def create_job(self, data: JobCreate) -> dict:
        logger.info("Creating job listing: title=%s", data.title)
        return self.supabase.create_job(data.model_dump())

    def update_job(self, job_id: UUID, data: JobUpdate) -> dict:
        logger.info("Updating job listing: id=%s", job_id)
        return self.supabase.update_job(job_id, data.model_dump(exclude_unset=True))

    def delete_job(self, job_id: UUID) -> dict:
        logger.info("Deleting job listing: id=%s", job_id)
        return self.supabase.delete_job(job_id)

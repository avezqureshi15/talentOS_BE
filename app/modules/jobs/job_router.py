from uuid import UUID

from fastapi import APIRouter, status

from app.core.config import settings
from app.modules.jobs.job_schema import JobCreate, JobUpdate
from app.modules.jobs.job_service import JobService

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/jobs", tags=["jobs"])


@router.get("/")
def get_all_jobs():
    service = JobService()
    return service.get_all_jobs()


@router.get("/{job_id}")
def get_job_by_id(job_id: UUID):
    service = JobService()
    return service.get_job_by_id(job_id)


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_job(data: JobCreate):
    service = JobService()
    return service.create_job(data)


@router.put("/{job_id}")
def update_job(job_id: UUID, data: JobUpdate):
    service = JobService()
    return service.update_job(job_id, data)


@router.delete("/{job_id}")
def delete_job(job_id: UUID):
    service = JobService()
    return service.delete_job(job_id)

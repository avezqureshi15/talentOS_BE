from datetime import datetime, timezone
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.job_posting import JobPosting
from app.schemas.job_posting import JobPostingCreate, JobPostingUpdate
from app.services.audit_service import AuditService
from app.services.careers_service import CareersService


class JobService:
    @staticmethod
    async def get_or_404(db: AsyncSession, job_id: UUID) -> JobPosting:
        result = await db.execute(select(JobPosting).where(JobPosting.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            raise HTTPException(status_code=404, detail="Job posting not found")
        return job

    @staticmethod
    async def create(
        db: AsyncSession, data: JobPostingCreate, actor_email: str
    ) -> JobPosting:
        job = JobPosting(**data.model_dump(), created_by=actor_email)
        db.add(job)
        await db.flush()

        await AuditService.log(
            db=db,
            entity_type="job_posting",
            entity_id=job.id,
            event_type="JOB_CREATED",
            actor_email=actor_email,
            payload={"title": job.title, "stream": job.stream, "band": job.band},
        )
        return job

    @staticmethod
    async def update(
        db: AsyncSession, job: JobPosting, data: JobPostingUpdate, actor_email: str
    ) -> JobPosting:
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(job, field, value)

        await AuditService.log(
            db=db,
            entity_type="job_posting",
            entity_id=job.id,
            event_type="JOB_UPDATED",
            actor_email=actor_email,
            payload=data.model_dump(exclude_none=True),
        )
        return job

    @staticmethod
    async def publish(db: AsyncSession, job: JobPosting, actor_email: str) -> JobPosting:
        if job.status not in ("draft", "bench_check"):
            raise HTTPException(status_code=400, detail=f"Cannot publish job in status: {job.status}")

        # Push to careers page Supabase
        careers_id = await CareersService.publish_job(job)
        job.careers_page_id = careers_id
        job.status = "active"
        job.published_at = datetime.now(timezone.utc)

        await AuditService.log(
            db=db,
            entity_type="job_posting",
            entity_id=job.id,
            event_type="JOB_PUBLISHED",
            actor_email=actor_email,
            payload={"careers_page_id": careers_id, "title": job.title},
        )
        return job

    @staticmethod
    async def fill_internal(db: AsyncSession, job: JobPosting, actor_email: str) -> JobPosting:
        job.status = "filled_internal"
        job.closed_at = datetime.now(timezone.utc)

        await AuditService.log(
            db=db,
            entity_type="job_posting",
            entity_id=job.id,
            event_type="JOB_FILLED_INTERNAL",
            actor_email=actor_email,
            payload={"title": job.title},
        )
        return job

    @staticmethod
    async def close(db: AsyncSession, job: JobPosting, actor_email: str) -> JobPosting:
        job.status = "closed"
        job.closed_at = datetime.now(timezone.utc)

        await AuditService.log(
            db=db,
            entity_type="job_posting",
            entity_id=job.id,
            event_type="JOB_CLOSED",
            actor_email=actor_email,
            payload={"title": job.title},
        )
        return job

    @staticmethod
    async def update_threshold(
        db: AsyncSession, job: JobPosting, threshold: int, actor_email: str
    ) -> JobPosting:
        old = job.ats_threshold
        job.ats_threshold = threshold

        await AuditService.log(
            db=db,
            entity_type="job_posting",
            entity_id=job.id,
            event_type="THRESHOLD_CHANGED",
            actor_email=actor_email,
            payload={"old_threshold": old, "new_threshold": threshold},
        )
        return job

from uuid import UUID
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.candidate import Candidate
from app.models.job_posting import JobPosting
from app.schemas.application import ApplicationSubmitIn
from app.workers.resume_worker import process_resume_task


class ApplicationService:
    @staticmethod
    async def receive(body: ApplicationSubmitIn, background_tasks: BackgroundTasks) -> UUID:
        """
        Receive application, create candidate record, queue evaluation.
        Returns candidate ID immediately.
        """
        async with AsyncSessionLocal() as db:
            # Verify job exists and is active
            from sqlalchemy import select
            result = await db.execute(
                select(JobPosting).where(
                    JobPosting.id == body.job_posting_id,
                    JobPosting.status == "active",
                )
            )
            job = result.scalar_one_or_none()
            if not job:
                raise HTTPException(status_code=404, detail="Job not found or no longer active")

            # Create candidate record
            candidate = Candidate(
                job_posting_id=body.job_posting_id,
                name=body.name,
                email=body.email,
                phone=body.phone,
                resume_url=body.resume_url,
                status="evaluating",
            )
            db.add(candidate)

            # Increment application counter
            job.total_applications += 1

            await db.commit()
            await db.refresh(candidate)
            candidate_id = candidate.id

        # Queue Celery task for async evaluation
        process_resume_task.delay(str(candidate_id))

        return candidate_id

from datetime import datetime, timezone
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.candidate import Candidate
from app.models.job_posting import JobPosting
from app.services.audit_service import AuditService


class ShortlistService:
    @staticmethod
    async def add(db: AsyncSession, candidate_id: UUID, actor_email: str) -> Candidate:
        result = await db.execute(select(Candidate).where(Candidate.id == candidate_id))
        candidate = result.scalar_one_or_none()
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")

        candidate.is_shortlisted = True
        candidate.status = "shortlisted"
        candidate.shortlisted_by = actor_email
        candidate.shortlisted_at = datetime.now(timezone.utc)

        # Update job counter
        job_result = await db.execute(
            select(JobPosting).where(JobPosting.id == candidate.job_posting_id)
        )
        job = job_result.scalar_one_or_none()
        if job:
            job.total_shortlisted += 1

        await AuditService.log(
            db=db,
            entity_type="candidate",
            entity_id=candidate_id,
            event_type="CANDIDATE_SHORTLISTED",
            actor_email=actor_email,
            payload={
                "name": candidate.name,
                "fit_score": float(candidate.fit_score or 0),
                "shortlisted_by": actor_email,
            },
        )
        return candidate

    @staticmethod
    async def remove(db: AsyncSession, candidate_id: UUID, actor_email: str) -> Candidate:
        result = await db.execute(select(Candidate).where(Candidate.id == candidate_id))
        candidate = result.scalar_one_or_none()
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")

        candidate.is_shortlisted = False
        candidate.status = "evaluated"

        job_result = await db.execute(
            select(JobPosting).where(JobPosting.id == candidate.job_posting_id)
        )
        job = job_result.scalar_one_or_none()
        if job and job.total_shortlisted > 0:
            job.total_shortlisted -= 1

        await AuditService.log(
            db=db,
            entity_type="candidate",
            entity_id=candidate_id,
            event_type="CANDIDATE_REMOVED_FROM_SHORTLIST",
            actor_email=actor_email,
            payload={"name": candidate.name},
        )
        return candidate

    @staticmethod
    async def override_score(
        db: AsyncSession,
        candidate_id: UUID,
        new_score: float,
        reason: str,
        actor_email: str,
    ) -> Candidate:
        result = await db.execute(select(Candidate).where(Candidate.id == candidate_id))
        candidate = result.scalar_one_or_none()
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")

        old_score = float(candidate.fit_score or 0)
        candidate.hr_override = True
        candidate.hr_override_score = new_score
        candidate.hr_override_reason = reason
        candidate.hr_override_by = actor_email
        candidate.fit_score = new_score

        await AuditService.log(
            db=db,
            entity_type="candidate",
            entity_id=candidate_id,
            event_type="SCORE_OVERRIDDEN",
            actor_email=actor_email,
            payload={
                "name": candidate.name,
                "original_score": old_score,
                "new_score": new_score,
                "reason": reason,
            },
        )
        return candidate

    @staticmethod
    async def confirm(db: AsyncSession, job_id: UUID, actor_email: str) -> dict:
        """Lock the shortlist — mark all shortlisted candidates as screening_queued."""
        result = await db.execute(
            select(Candidate).where(
                Candidate.job_posting_id == job_id,
                Candidate.is_shortlisted == True,
            )
        )
        candidates = result.scalars().all()

        if not candidates:
            raise HTTPException(status_code=400, detail="No shortlisted candidates to confirm")

        for c in candidates:
            c.status = "screening_queued"

        await AuditService.log(
            db=db,
            entity_type="job_posting",
            entity_id=job_id,
            event_type="SHORTLIST_CONFIRMED",
            actor_email=actor_email,
            payload={"total_confirmed": len(candidates)},
        )

        return {
            "job_posting_id": job_id,
            "total_confirmed": len(candidates),
            "status": "screening_queued",
        }

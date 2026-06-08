from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from uuid import UUID

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import AllowedUser
from app.models.job_posting import JobPosting
from app.schemas.job_posting import JobPostingCreate, JobPostingOut, JobPostingUpdate, ThresholdUpdateIn
from app.services.job_service import JobService
from app.services.audit_service import AuditService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=List[JobPostingOut])
async def list_jobs(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: AllowedUser = Depends(get_current_user),
):
    query = select(JobPosting).order_by(JobPosting.created_at.desc())
    if status:
        query = query.where(JobPosting.status == status)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{job_id}", response_model=JobPostingOut)
async def get_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: AllowedUser = Depends(get_current_user),
):
    job = await JobService.get_or_404(db, job_id)
    return job


@router.put("/{job_id}", response_model=JobPostingOut)
async def update_job(
    job_id: UUID,
    body: JobPostingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: AllowedUser = Depends(get_current_user),
):
    job = await JobService.get_or_404(db, job_id)
    updated = await JobService.update(db, job, body, actor_email=current_user.email)
    return updated


@router.post("/{job_id}/publish", response_model=JobPostingOut)
async def publish_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: AllowedUser = Depends(get_current_user),
):
    job = await JobService.get_or_404(db, job_id)
    published = await JobService.publish(db, job, actor_email=current_user.email)
    return published


@router.post("/{job_id}/fill-internal", response_model=JobPostingOut)
async def fill_internal(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: AllowedUser = Depends(get_current_user),
):
    job = await JobService.get_or_404(db, job_id)
    closed = await JobService.fill_internal(db, job, actor_email=current_user.email)
    return closed


@router.post("/{job_id}/close", response_model=JobPostingOut)
async def close_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: AllowedUser = Depends(get_current_user),
):
    job = await JobService.get_or_404(db, job_id)
    closed = await JobService.close(db, job, actor_email=current_user.email)
    return closed


@router.put("/{job_id}/threshold", response_model=JobPostingOut)
async def update_threshold(
    job_id: UUID,
    body: ThresholdUpdateIn,
    db: AsyncSession = Depends(get_db),
    current_user: AllowedUser = Depends(get_current_user),
):
    job = await JobService.get_or_404(db, job_id)
    updated = await JobService.update_threshold(
        db, job, body.ats_threshold, actor_email=current_user.email
    )
    return updated

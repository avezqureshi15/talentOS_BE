from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from uuid import UUID

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import AllowedUser
from app.models.candidate import Candidate
from app.schemas.candidate import CandidateOut, ScoreOverrideIn, ShortlistConfirmOut
from app.services.shortlist_service import ShortlistService
from app.services.audit_service import AuditService

router = APIRouter(tags=["candidates"])


@router.get("/jobs/{job_id}/candidates/shortlisted", response_model=List[CandidateOut])
async def get_shortlisted(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: AllowedUser = Depends(get_current_user),
):
    result = await db.execute(
        select(Candidate)
        .where(Candidate.job_posting_id == job_id, Candidate.is_shortlisted == True)
        .order_by(Candidate.fit_score.desc())
    )
    return result.scalars().all()


@router.get("/jobs/{job_id}/candidates/all", response_model=List[CandidateOut])
async def get_all_candidates(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: AllowedUser = Depends(get_current_user),
):
    result = await db.execute(
        select(Candidate)
        .where(Candidate.job_posting_id == job_id)
        .order_by(Candidate.fit_score.desc().nulls_last())
    )
    return result.scalars().all()


@router.get("/candidates/{candidate_id}", response_model=CandidateOut)
async def get_candidate(
    candidate_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: AllowedUser = Depends(get_current_user),
):
    result = await db.execute(
        select(Candidate).where(Candidate.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate


@router.post("/candidates/{candidate_id}/shortlist", response_model=CandidateOut)
async def add_to_shortlist(
    candidate_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: AllowedUser = Depends(get_current_user),
):
    candidate = await ShortlistService.add(db, candidate_id, actor_email=current_user.email)
    return candidate


@router.delete("/candidates/{candidate_id}/shortlist", response_model=CandidateOut)
async def remove_from_shortlist(
    candidate_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: AllowedUser = Depends(get_current_user),
):
    candidate = await ShortlistService.remove(db, candidate_id, actor_email=current_user.email)
    return candidate


@router.put("/candidates/{candidate_id}/score-override", response_model=CandidateOut)
async def override_score(
    candidate_id: UUID,
    body: ScoreOverrideIn,
    db: AsyncSession = Depends(get_db),
    current_user: AllowedUser = Depends(get_current_user),
):
    candidate = await ShortlistService.override_score(
        db, candidate_id, body.new_score, body.reason, actor_email=current_user.email
    )
    return candidate


@router.post("/jobs/{job_id}/shortlist/confirm", response_model=ShortlistConfirmOut)
async def confirm_shortlist(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: AllowedUser = Depends(get_current_user),
):
    result = await ShortlistService.confirm(db, job_id, actor_email=current_user.email)
    return result

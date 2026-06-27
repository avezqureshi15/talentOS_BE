from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.modules.applications.application_schema import (
    ApplicationCreate,
    PaginatedEvaluatedCandidatesResponse,
)
from app.modules.applications.application_service import ApplicationService

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/applications", tags=["applications"])


@router.get("/", response_model=PaginatedEvaluatedCandidatesResponse)
def get_all_applications(
    job_id: str | None = Query(default=None, description="Filter by job ID"),
    status: str | None = Query(default=None, description="Filter by evaluation status (SHORTLISTED, REJECTED, etc.)"),
    min_score: int | None = Query(default=None, ge=0, le=100, description="Minimum ATS score filter"),
    max_score: int | None = Query(default=None, ge=0, le=100, description="Maximum ATS score filter"),
    limit: int = Query(default=20, ge=1, le=100, description="Number of candidates to return"),
    offset: int = Query(default=0, ge=0, description="Number of candidates to skip"),
    db: Session = Depends(get_db),
):
    service = ApplicationService(db)
    return service.get_applications_paginated(
        job_id=job_id,
        status_filter=status,
        min_score=min_score,
        max_score=max_score,
        limit=limit,
        offset=offset,
    )


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_application(data: ApplicationCreate):
    service = ApplicationService()
    return service.create_application(data)

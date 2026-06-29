from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.modules.applications.application_schema import (
    ApplicationCreate,
    EvaluatedCandidate,
    PaginatedEvaluatedCandidatesResponse,
)
from app.modules.applications.application_service import ApplicationService

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/applications", tags=["applications"])


@router.get("/{application_id}", response_model=EvaluatedCandidate)
def get_application_by_id(
    application_id: str,
    db: Session = Depends(get_db),
):
    service = ApplicationService(db)
    result = service.get_application_by_id(application_id)
    if not result:
        raise HTTPException(status_code=404, detail="Application not found")
    return result


@router.get("/", response_model=PaginatedEvaluatedCandidatesResponse)
def get_all_applications(
    job_id: str | None = Query(default=None, description="Filter by job ID"),
    status: str | None = Query(default=None, description="Filter by evaluation status (SHORTLISTED, REJECTED, etc.)"),
    schedule: str | None = Query(default=None, description="Filter by schedule status (scheduled, unscheduled)"),
    min_score: int | None = Query(default=None, ge=0, le=100, description="Minimum ATS score filter"),
    max_score: int | None = Query(default=None, ge=0, le=100, description="Maximum ATS score filter"),
    date_from: str | None = Query(default=None, description="Filter by created date >= (ISO 8601)"),
    date_to: str | None = Query(default=None, description="Filter by created date <= (ISO 8601)"),
    limit: int = Query(default=20, ge=1, le=100, description="Number of candidates to return"),
    offset: int = Query(default=0, ge=0, description="Number of candidates to skip"),
    db: Session = Depends(get_db),
):
    service = ApplicationService(db)
    return service.get_applications_paginated(
        job_id=job_id,
        status_filter=status,
        schedule_filter=schedule,
        min_score=min_score,
        max_score=max_score,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_application(data: ApplicationCreate):
    service = ApplicationService()
    return service.create_application(data)

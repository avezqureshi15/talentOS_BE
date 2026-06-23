from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.modules.applications.application_schema import (
    ApplicationCreate,
    EvaluatedCandidatesResponse,
)
from app.modules.applications.application_service import ApplicationService

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/applications", tags=["applications"])


@router.get("/", response_model=EvaluatedCandidatesResponse)
def get_all_applications(
    job_id: str | None = Query(default=None, description="Filter by job ID"),
    status: str | None = Query(default=None, description="Filter by evaluation status (SHORTLISTED, REJECTED, etc.)"),
    db: Session = Depends(get_db),
):
    service = ApplicationService(db)
    return service.get_all_applications(job_id=job_id, status_filter=status)


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_application(data: ApplicationCreate):
    service = ApplicationService()
    return service.create_application(data)

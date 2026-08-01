from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.job_access import can_create_job, require_job_access
from app.core.permissions import Permission
from app.db.session import get_db
from app.modules.auth.auth_dependencies import get_current_user
from app.modules.auth.auth_schema import UserInfo
from app.modules.hiring_requests.hiring_request_schema import HiringRequestCreate, HiringRequestUpdate
from app.modules.hiring_requests.hiring_request_service import HiringRequestService

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/hiring-requests", tags=["hiring-requests"])


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_hiring_request(
    data: HiringRequestCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    if not can_create_job(db, current_user):
        raise HTTPException(status_code=403, detail="Missing required permission: hiring_request.create")
    service = HiringRequestService(db)
    return service.create_hiring_request(data, background_tasks, current_user=current_user)


@router.get("/")
def get_all_hiring_requests(
    q: str | None = Query(None, description="Search query for title, department, or location"),
    department: str | None = Query(None, description="Filter by department"),
    location: str | None = Query(None, description="Filter by location"),
    type: str | None = Query(None, description="Filter by type"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    created_from: datetime | None = Query(None, description="Filter by created_at >= this date"),
    created_to: datetime | None = Query(None, description="Filter by created_at <= this date"),
    tenant_id: int | None = Query(None, description="Superadmin-only: filter by tenant"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=50, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    if tenant_id is not None and current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="tenant_id filter is restricted to superadmin")
    service = HiringRequestService(db)
    return service.get_all_hiring_requests(
        search=q,
        department=department,
        location=location,
        type=type,
        is_active=is_active,
        created_from=created_from,
        created_to=created_to,
        page=page,
        per_page=per_page,
        tenant_id=tenant_id,
        current_user=current_user,
    )


@router.get("/departments")
def get_departments(
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    service = HiringRequestService(db)
    return service.get_departments(current_user=current_user)


@router.get("/locations")
def get_locations(
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    service = HiringRequestService(db)
    return service.get_locations(current_user=current_user)


@router.get("/types")
def get_types(
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    service = HiringRequestService(db)
    return service.get_types(current_user=current_user)


@router.patch("/{hiring_request_id}/status")
def toggle_hiring_request_status(
    hiring_request_id: UUID,
    db: Session = Depends(get_db),
    _: object = Depends(require_job_access(min_role="recruiter")),
):
    service = HiringRequestService(db)
    return service.toggle_hiring_request_status(hiring_request_id)


@router.get("/{hiring_request_id}")
def get_hiring_request_by_id(
    hiring_request_id: UUID,
    db: Session = Depends(get_db),
    _: object = Depends(require_job_access()),
):
    service = HiringRequestService(db)
    return service.get_hiring_request_by_id(hiring_request_id)


@router.put("/{hiring_request_id}")
def update_hiring_request(
    hiring_request_id: UUID,
    data: HiringRequestUpdate,
    db: Session = Depends(get_db),
    _: object = Depends(require_job_access(min_role="recruiter")),
):
    service = HiringRequestService(db)
    return service.update_hiring_request(hiring_request_id, data)


@router.delete("/{hiring_request_id}")
def delete_hiring_request(
    hiring_request_id: UUID,
    db: Session = Depends(get_db),
    _: object = Depends(require_job_access(min_role="job_owner", permission=Permission.HIRING_REQUEST_DELETE)),
):
    service = HiringRequestService(db)
    return service.delete_hiring_request(hiring_request_id)

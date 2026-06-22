from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.modules.hiring_requests.hiring_request_schema import HiringRequestCreate, HiringRequestUpdate
from app.modules.hiring_requests.hiring_request_service import HiringRequestService
from app.modules.hiring_requests.hiring_request_excel_service import fetch_applications, generate_excel_bytes

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/hiring-requests", tags=["hiring-requests"])


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_hiring_request(data: HiringRequestCreate, db: Session = Depends(get_db)):
    service = HiringRequestService(db)
    return service.create_hiring_request(data)


@router.get("/")
def get_all_hiring_requests(
    q: str | None = Query(None, description="Search query for title, department, or location"),
    department: str | None = Query(None, description="Filter by department"),
    location: str | None = Query(None, description="Filter by location"),
    type: str | None = Query(None, description="Filter by type"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    created_from: datetime | None = Query(None, description="Filter by created_at >= this date"),
    created_to: datetime | None = Query(None, description="Filter by created_at <= this date"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=50, description="Items per page"),
    db: Session = Depends(get_db),
):
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
    )


@router.get("/departments")
def get_departments(db: Session = Depends(get_db)):
    service = HiringRequestService(db)
    return service.get_departments()


@router.get("/locations")
def get_locations(db: Session = Depends(get_db)):
    service = HiringRequestService(db)
    return service.get_locations()


@router.get("/types")
def get_types(db: Session = Depends(get_db)):
    service = HiringRequestService(db)
    return service.get_types()


@router.patch("/{hiring_request_id}/status")
def toggle_hiring_request_status(hiring_request_id: UUID, db: Session = Depends(get_db)):
    service = HiringRequestService(db)
    return service.toggle_hiring_request_status(hiring_request_id)


@router.get("/{hiring_request_id}")
def get_hiring_request_by_id(hiring_request_id: UUID, db: Session = Depends(get_db)):
    service = HiringRequestService(db)
    return service.get_hiring_request_by_id(hiring_request_id)


@router.put("/{hiring_request_id}")
def update_hiring_request(hiring_request_id: UUID, data: HiringRequestUpdate, db: Session = Depends(get_db)):
    service = HiringRequestService(db)
    return service.update_hiring_request(hiring_request_id, data)


@router.delete("/{hiring_request_id}")
def delete_hiring_request(hiring_request_id: UUID, db: Session = Depends(get_db)):
    service = HiringRequestService(db)
    return service.delete_hiring_request(hiring_request_id)


@router.get("/{hiring_request_id}/export")
def export_hiring_request_excel(hiring_request_id: UUID, db: Session = Depends(get_db)):
    service = HiringRequestService(db)
    job_data = service.get_hiring_request_by_id(hiring_request_id)
    job = job_data["data"]
    supabase_job_id = job.get("supabase_job_id")

    all_apps = fetch_applications()
    if supabase_job_id:
        filtered = [a for a in all_apps if str(a.get("job_id", "")) == str(supabase_job_id)]
    else:
        filtered = []

    buf = generate_excel_bytes(job, filtered)
    safe_title = job.get("title", "export").replace("/", "_").replace("\\", "_")
    filename = f"{safe_title}_applicants.xlsx"

    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

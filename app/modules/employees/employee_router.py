from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.modules.employees.employee_schema import PaginatedEmployeeFormStatusResponse
from app.modules.employees.employee_service import EmployeeService

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/employees", tags=["employees"])


@router.get("/form-status", response_model=PaginatedEmployeeFormStatusResponse)
def get_form_status(
    type: str = Query(..., pattern="^(SLOTS|REVIEW)$"),
    status: str = Query(..., pattern="^(SENT|SUBMITTED|EXPIRED)$"),
    emp_ids: list[str] = Query(default=[]),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    service = EmployeeService(db)
    return service.get_form_status(
        form_type=type,
        status=status,
        emp_ids=emp_ids,
        page=page,
        per_page=per_page,
    )

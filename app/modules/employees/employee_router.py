from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.authorization import require_permission
from app.core.config import settings
from app.core.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.core.permissions import Permission
from app.db.session import get_db
from app.modules.auth.auth_dependencies import get_current_user
from app.modules.auth.auth_schema import UserInfo
from app.modules.employees.employee_directory_repository import EmployeeDirectoryRepository
from app.modules.employees.employee_directory_schema import (
    CreateEmployeeRequest,
    EmployeeResponse,
    PaginatedEmployeeResponse,
    UpdateEmployeeRequest,
)
from app.modules.employees.employee_model import Employee
from app.modules.employees.employee_schema import PaginatedEmployeeFormStatusResponse
from app.modules.employees.employee_service import EmployeeService
from app.modules.employees.excel.import_service import EmployeeImportService
from app.modules.users.user_model import User

_XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class EmployeeImportRowError(BaseModel):
    row: int
    error: str


class EmployeeImportSummary(BaseModel):
    total: int
    imported: int
    skipped_duplicates: int
    failed: list[EmployeeImportRowError]


def _user_id_map(db, employee_ids: list[int]) -> dict[int, int]:
    """Reverse lookup employees.id → users.id for a batch of employees."""
    if not employee_ids:
        return {}
    rows = (
        db.query(User.employee_id, User.id)
        .filter(User.employee_id.in_(employee_ids))
        .all()
    )
    return {emp_id: uid for emp_id, uid in rows}


def _to_response(e: Employee, user_id: int | None, slots_count: int = 0) -> EmployeeResponse:
    item = EmployeeResponse.model_validate(e)
    item.user_id = user_id
    if slots_count:
        item.slots_count = slots_count
        item.has_slots = True
    return item

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/employees", tags=["employees"])


@router.post("/import", response_model=EmployeeImportSummary)
def import_employees(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.USER_MANAGE)),
):
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Only .xlsx files are supported")
    tenant_id = None if current_user.role == "superadmin" else current_user.tenant_id
    return EmployeeImportService(db).import_employees(file.file, tenant_id=tenant_id)


@router.get("/import-template")
def import_template(
    current_user: UserInfo = Depends(require_permission(Permission.USER_MANAGE)),
):
    _ = current_user  # permission checked; user unused
    buf, filename = EmployeeImportService.build_import_template()
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type=_XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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


@router.get("/benched")
def get_benched_employees(
    designation: str = Query(...),
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    repo = EmployeeDirectoryRepository(db)
    tenant_id = None if current_user.role == "superadmin" else current_user.tenant_id
    employees = repo.get_benched_by_designation(designation, tenant_id=tenant_id)
    uid_map = _user_id_map(db, [e.id for e in employees])
    data = [_to_response(e, uid_map.get(e.id)) for e in employees]
    return {"data": data, "count": len(data)}


@router.get("/{emp_id}", response_model=EmployeeResponse | None)
def get_employee_by_emp_id(
    emp_id: str,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    repo = EmployeeDirectoryRepository(db)
    employee = repo.get_by_emp_id(emp_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    uid_map = _user_id_map(db, [employee.id])
    return _to_response(employee, uid_map.get(employee.id))


@router.get("/", response_model=PaginatedEmployeeResponse)
def list_employees(
    q: str | None = Query(None, description="Search query"),
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    slotsInfo: bool = Query(False, description="Include slot availability info and sort by slot count"),
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.EMPLOYEE_VIEW)),
):
    repo = EmployeeDirectoryRepository(db)

    tenant_id: int | None = current_user.tenant_id
    if current_user.role == "superadmin":
        tenant_id = None

    result, total = repo.search_paginated(
        query=q,
        page=page,
        per_page=per_page,
        slots_info=slotsInfo,
        tenant_id=tenant_id,
    )

    employees: list[Employee] = (
        [row[0] for row in result] if slotsInfo else list(result)  # type: ignore[assignment]
    )
    uid_map = _user_id_map(db, [e.id for e in employees])

    if slotsInfo:
        data: list[EmployeeResponse] = [
            _to_response(e, uid_map.get(e.id), slots_count=count) for e, count in result
        ]
    else:
        data = [_to_response(e, uid_map.get(e.id)) for e in employees]

    has_more = (page * per_page) < total
    return PaginatedEmployeeResponse(
        data=data, total=total, page=page, per_page=per_page, has_more=has_more
    )


@router.post("/", response_model=EmployeeResponse, status_code=201)
def create_employee(
    body: CreateEmployeeRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.USER_MANAGE)),
):
    repo = EmployeeDirectoryRepository(db)

    if repo.get_by_emp_id(body.emp_id):
        raise HTTPException(status_code=409, detail="Employee with this emp_id already exists")
    if repo.get_by_email(body.email):
        raise HTTPException(status_code=409, detail="Employee with this email already exists")

    tenant_id = None if current_user.role == "superadmin" else current_user.tenant_id
    employee = repo.create(tenant_id=tenant_id, **body.model_dump(exclude_unset=True))
    return _to_response(employee, _user_id_map(db, [employee.id]).get(employee.id))


@router.patch("/{emp_id}", response_model=EmployeeResponse)
def update_employee(
    emp_id: str,
    body: UpdateEmployeeRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.USER_MANAGE)),
):
    repo = EmployeeDirectoryRepository(db)
    employee = repo.get_by_emp_id(emp_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    if current_user.role != "superadmin" and employee.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="No access to this employee")

    updated = repo.update(employee, **body.model_dump(exclude_unset=True))
    return _to_response(updated, _user_id_map(db, [updated.id]).get(updated.id))


@router.delete("/{emp_id}", response_model=EmployeeResponse)
def deactivate_employee(
    emp_id: str,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.USER_MANAGE)),
):
    repo = EmployeeDirectoryRepository(db)
    employee = repo.get_by_emp_id(emp_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    if current_user.role != "superadmin" and employee.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="No access to this employee")

    deactivated = repo.soft_delete(employee)
    return _to_response(deactivated, _user_id_map(db, [deactivated.id]).get(deactivated.id))

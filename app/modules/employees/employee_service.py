from sqlalchemy.orm import Session

from app.modules.employees.employee_repository import EmployeeRepository
from app.modules.employees.employee_schema import (
    EmployeeFormStatusItem,
    PaginatedEmployeeFormStatusResponse,
)


class EmployeeService:
    def __init__(self, db: Session):
        self.repository = EmployeeRepository(db)

    def get_form_status(
        self,
        form_type: str,
        status: str,
        emp_ids: list[str],
        page: int,
        per_page: int,
    ) -> PaginatedEmployeeFormStatusResponse:
        rows, total = self.repository.list_form_status(
            form_type=form_type,
            status=status,
            emp_ids=emp_ids,
            page=page,
            per_page=per_page,
        )
        data = [
            EmployeeFormStatusItem(
                emp_id=row[0],
                name=row[1] or row[0],
                email=row[2] or "",
                type=row[3],
                status=row[4],
                last_sent_at=row[5],
                updated_at=row[6],
            )
            for row in rows
        ]
        return PaginatedEmployeeFormStatusResponse(
            data=data,
            total=total,
            page=page,
            per_page=per_page,
            has_more=(page * per_page) < total,
        )

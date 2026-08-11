from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.modules.employees.employee_directory_repository import EmployeeDirectoryRepository
from app.modules.forms.form_mail import send_slot_mail_task
from app.modules.forms.form_schema import AskFormRequest, AskFormResponse
from app.modules.forms.form_service import FormService

router = APIRouter(prefix=settings.API_V1_PREFIX, tags=["forms"])


@router.post("/ask-form", response_model=AskFormResponse)
def ask_form(
    data: AskFormRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    if data.type == "REVIEW":
        return _generate_review_forms(data, db)

    service = FormService(db)
    response, mail_tasks = service.ask_form_batch(data.emp_ids, data.type, requester_name=data.requester_name)
    for task in mail_tasks:
        background_tasks.add_task(
            send_slot_mail_task, task.user_id, task.form_id, requester_name=data.requester_name
        )
    return response


def _generate_review_forms(data: AskFormRequest, db: Session) -> AskFormResponse:
    from app.modules.rounds.round_service import RoundService
    from app.modules.rounds.round_schema import RoundDetailResponse

    if not data.round_id:
        raise HTTPException(status_code=400, detail="round_id is required for REVIEW type")
    if not data.candidate_id:
        raise HTTPException(status_code=400, detail="candidate_id is required for REVIEW type")

    round_svc = RoundService(db)
    round_detail = round_svc.get_round_detail(data.round_id)
    if not round_detail:
        raise HTTPException(status_code=404, detail="Round not found")

    employees = EmployeeDirectoryRepository(db)
    service = FormService(db)
    results: list[AskFormResultItem] = []

    for emp_id in data.emp_ids:
        employee = employees.get_by_emp_id(emp_id)
        if not employee:
            results.append(AskFormResultItem(emp_id=emp_id, status="FAILED", message="Employee not found"))
            continue
        try:
            service.generate_review_form(
                emp_id=emp_id,
                round_id=data.round_id,
                candidate_id=data.candidate_id,
                candidate_name=round_detail.candidate or "Candidate",
                round_name=round_detail.round or "Interview",
                interviewer_name=employee.name or emp_id,
                interviewer_email=employee.email or "",
                requester_name=data.requester_name,
            )
            results.append(AskFormResultItem(emp_id=emp_id, status="SUCCESS", message="Review form sent"))
        except ValueError as exc:
            results.append(AskFormResultItem(emp_id=emp_id, status="FAILED", message=str(exc)))

    return AskFormResponse(message="Review forms generated", results=results)

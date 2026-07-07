from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
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
    service = FormService(db)
    response, mail_tasks = service.ask_form_batch(data.emp_ids, data.type)
    for task in mail_tasks:
        background_tasks.add_task(send_slot_mail_task, task.emp_id, task.form_id)
    return response

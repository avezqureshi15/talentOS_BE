from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import exc as sa_exc
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.modules.forms.form_mail import (
    detail_to_message,
    send_review_mail_task,
    send_slot_mail_task,
)
from app.modules.forms.form_schema import (
    FormSubmitResponse,
    FormValidateResponse,
    NotifyFormRequest,
    NotifyFormResponse,
)
from app.modules.forms.form_service import FormService
from app.modules.forms.form_model import FormType

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/forms", tags=["forms"])


@router.get("/validate/{form_id}", response_model=FormValidateResponse)
def validate_form(form_id: UUID, db: Session = Depends(get_db)):
    service = FormService(db)
    return service.validate_form(form_id)


@router.post("/notify", response_model=NotifyFormResponse)
def notify_form(
    data: NotifyFormRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    service = FormService(db)
    try:
        form, detail = service.notify_form(
            user_id=data.user_id,
            form_type=data.type,
            is_reminder=data.reminder,
        )
    except ValueError as exc:
        raise HTTPException(status_code=429, detail=str(exc))

    try:
        if data.type == FormType.REVIEW.value:
            background_tasks.add_task(
                send_review_mail_task, data.user_id, form.id,
                None, None, None, is_reminder=data.reminder,
            )
        else:
            background_tasks.add_task(
                send_slot_mail_task, data.user_id, form.id,
                is_reminder=data.reminder,
            )
        db.commit()
    except sa_exc.SQLAlchemyError:
        db.rollback()
        raise

    return NotifyFormResponse(
        message=detail_to_message(detail),
        detail=detail,
        form_id=form.id,
    )


@router.post("/{form_id}/remind", response_model=NotifyFormResponse)
def remind_form(
    form_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    service = FormService(db)
    try:
        form, detail = service.remind_by_form(form_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    try:
        if form.type == FormType.REVIEW.value:
            background_tasks.add_task(
                send_review_mail_task, form.user.id, form.id,
                None, None, None, is_reminder=True,
            )
        else:
            background_tasks.add_task(
                send_slot_mail_task, form.user.id, form.id,
                is_reminder=True,
            )
        db.commit()
    except sa_exc.SQLAlchemyError:
        db.rollback()
        raise

    return NotifyFormResponse(
        message=detail_to_message(detail),
        detail=detail,
        form_id=form.id,
    )


@router.post("/{form_id}/submit", response_model=FormSubmitResponse)
def submit_form(form_id: UUID, db: Session = Depends(get_db)):
    service = FormService(db)
    try:
        return service.submit_form(form_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

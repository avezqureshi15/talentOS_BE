from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import exc as sa_exc
from sqlalchemy.orm import Session

from app.core.authorization import require_permission
from app.core.config import settings
from app.core.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.core.permissions import Permission
from app.db.session import get_db
from app.modules.auth.auth_dependencies import get_current_user
from app.modules.auth.auth_schema import UserInfo
from app.modules.forms.form_mail import (
    detail_to_message,
    send_review_mail_task,
    send_slot_mail_task,
)
from app.modules.forms.form_model import FormType
from app.modules.forms.form_schema import (
    FormSubmitResponse,
    FormValidateResponse,
    NotifyFormRequest,
    NotifyFormResponse,
    PaginatedPendingSlotFormsResponse,
)
from app.modules.forms.form_service import FormService

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/forms", tags=["forms"])


@router.get(
    "/slots/pending",
    response_model=PaginatedPendingSlotFormsResponse,
    dependencies=[Depends(require_permission(Permission.SLOT_VIEW_ALL))],
)
def list_pending_slot_forms(
    q: str | None = Query(None, description="Search by employee name, emp_id, or email"),
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    tenant_id = None if current_user.role == "superadmin" else current_user.tenant_id
    return FormService(db).list_pending_slot_forms(
        page=page,
        per_page=per_page,
        query=q,
        tenant_id=tenant_id,
    )


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
            requester_name=data.requester_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=429, detail=str(exc))

    try:
        # data.user_id is wire-name legacy; value is now an employees.id.
        if data.type == FormType.REVIEW.value:
            background_tasks.add_task(
                send_review_mail_task, data.user_id, form.id,
                None, None, None, is_reminder=data.reminder,
                requester_name=form.requested_by_name,
            )
        else:
            background_tasks.add_task(
                send_slot_mail_task, data.user_id, form.id,
                is_reminder=data.reminder,
                requester_name=form.requested_by_name,
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
                send_review_mail_task, form.employee_id, form.id,
                None, None, None, is_reminder=True,
                requester_name=form.requested_by_name,
            )
        else:
            background_tasks.add_task(
                send_slot_mail_task, form.employee_id, form.id,
                is_reminder=True,
                requester_name=form.requested_by_name,
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

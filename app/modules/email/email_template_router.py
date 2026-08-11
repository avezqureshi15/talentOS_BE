from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.authorization import require_permission
from app.core.config import settings
from app.core.permissions import Permission
from app.db.session import get_db
from app.modules.auth.auth_schema import UserInfo
from app.modules.email.email_template_schema import (
    EmailTemplateDetail,
    EmailTemplateListResponse,
    PreviewEmailTemplateRequest,
    PreviewEmailTemplateResponse,
    TestEmailTemplateRequest,
    TestEmailTemplateResponse,
    UpdateEmailTemplateRequest,
)
from app.modules.email.email_template_service import list_templates, get_template, update_template, render_preview, send_test

router = APIRouter(
    prefix=f"{settings.API_V1_PREFIX}/email/templates",
    tags=["email-templates"],
    dependencies=[Depends(require_permission(Permission.APPLICATION_VIEW))],
)


@router.get("", response_model=EmailTemplateListResponse)
def get_templates(db: Session = Depends(get_db)):
    return EmailTemplateListResponse(templates=list_templates(db))


@router.get("/{key}", response_model=EmailTemplateDetail)
def get_template_detail(key: str, db: Session = Depends(get_db)):
    try:
        return get_template(db, key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/preview", response_model=PreviewEmailTemplateResponse)
def preview_template(
    body: PreviewEmailTemplateRequest,
    db: Session = Depends(get_db),
):
    if not body.key:
        raise HTTPException(status_code=400, detail="key is required")
    try:
        subject, html = render_preview(
            db,
            body.key,
            subject_template=body.subject_template,
            body_html_template=body.body_html_template,
        )
        return PreviewEmailTemplateResponse(key=body.key, subject=subject, html=html)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.put("/{key}", response_model=EmailTemplateDetail)
def update_template_detail(
    key: str,
    body: UpdateEmailTemplateRequest,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.SETTINGS_EDIT)),
):
    try:
        return update_template(
            db,
            key,
            subject_template=body.subject_template,
            body_html_template=body.body_html_template,
            updated_by=current_user.email,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{key}/test", response_model=TestEmailTemplateResponse)
def test_template(
    key: str,
    body: TestEmailTemplateRequest,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(require_permission(Permission.SETTINGS_EDIT)),
):
    to_email = (body.to_email or current_user.email or "").strip()
    if not to_email:
        raise HTTPException(status_code=400, detail="No recipient email available")
    try:
        send_test(db, key, to_email)
        return TestEmailTemplateResponse(success=True, message="Test email sent", to_email=to_email)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.modules.forms.form_schema import FormValidateResponse
from app.modules.forms.form_service import FormService

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/forms", tags=["forms"])


@router.get("/validate/{form_id}", response_model=FormValidateResponse)
def validate_form(form_id: UUID, db: Session = Depends(get_db)):
    service = FormService(db)
    return service.validate_form(form_id)

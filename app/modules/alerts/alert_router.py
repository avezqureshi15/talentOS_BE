from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.modules.alerts.alert_schema import AlertResponse, PaginatedAlertResponse
from app.modules.alerts.alert_service import AlertService

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/alerts", tags=["alerts"])


@router.get("/", response_model=PaginatedAlertResponse)
def list_alerts(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=20, le=100),
    emp_id: str | None = Query(default=None),
    type: str | None = Query(default=None),
    is_read: bool | None = Query(default=None),
    db: Session = Depends(get_db),
):
    service = AlertService(db)
    return service.list_alerts(page=page, per_page=per_page, emp_id=emp_id, alert_type=type, is_read=is_read)


@router.patch("/{alert_id}/read", response_model=AlertResponse)
def mark_alert_read(alert_id: UUID, db: Session = Depends(get_db)):
    service = AlertService(db)
    return service.mark_alert_read(alert_id)

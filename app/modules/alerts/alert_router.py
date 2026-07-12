from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.modules.alerts.alert_schema import AlertListResponse, AlertResponse
from app.modules.alerts.alert_service import AlertService

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/alerts", tags=["alerts"])


@router.get("/", response_model=AlertListResponse)
def list_alerts(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    type: str | None = Query(default=None),
    is_read: bool | None = Query(default=False),
    db: Session = Depends(get_db),
):
    service = AlertService(db)
    return service.list_alerts_enriched(alert_type=type, page=page, per_page=per_page, is_read=is_read)


@router.patch("/{alert_id}/read", response_model=AlertResponse)
def mark_alert_read(alert_id: UUID, db: Session = Depends(get_db)):
    service = AlertService(db)
    return service.mark_alert_read(alert_id)

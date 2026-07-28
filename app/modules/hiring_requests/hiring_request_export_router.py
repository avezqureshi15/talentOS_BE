from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.authorization import require_permission
from app.core.config import settings
from app.core.permissions import Permission
from app.db.session import get_db
from app.modules.hiring_requests.excel import HiringRequestExportService

router = APIRouter(
    prefix=f"{settings.API_V1_PREFIX}/hiring-requests",
    tags=["hiring-requests"],
    dependencies=[Depends(require_permission(Permission.HIRING_REQUEST_VIEW))],
)


@router.get("/{hiring_request_id}/export")
def export_hiring_request_excel(hiring_request_id: UUID, db: Session = Depends(get_db)):
    buf, filename = HiringRequestExportService(db).export(hiring_request_id)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

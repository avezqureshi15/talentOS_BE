from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.authorization import require_permission
from app.core.config import settings
from app.core.permissions import Permission
from app.db.session import get_db
from app.modules.hiring_requests.excel.import_service import CandidateImportService

router = APIRouter(
    prefix=f"{settings.API_V1_PREFIX}/hiring-requests",
    tags=["hiring-requests"],
    dependencies=[Depends(require_permission(Permission.APPLICATION_WORKFLOW))],
)

_XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class ImportRowError(BaseModel):
    row: int
    error: str


class ImportSummary(BaseModel):
    total: int
    imported: int
    skipped_duplicates: int
    failed: list[ImportRowError]


@router.post("/{hiring_request_id}/import-candidates", response_model=ImportSummary)
def import_candidates(
    hiring_request_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Only .xlsx files are supported")
    result = CandidateImportService(db).import_candidates(hiring_request_id, file.file)
    return result


@router.get("/{hiring_request_id}/import-template")
def import_template(hiring_request_id: UUID, db: Session = Depends(get_db)):
    buf, filename = CandidateImportService(db).build_import_template(hiring_request_id)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type=_XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

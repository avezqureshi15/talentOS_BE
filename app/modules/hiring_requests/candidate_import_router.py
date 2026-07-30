from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.authorization import require_permission
from app.core.config import settings
from app.core.permissions import Permission
from app.db.session import get_db
from app.modules.hiring_requests.candidate_import_schema import ImportCandidatesResponse
from app.modules.hiring_requests.candidate_import_service import CandidateImportService

router = APIRouter(
    prefix=f"{settings.API_V1_PREFIX}/hiring-requests",
    tags=["hiring-requests"],
    dependencies=[Depends(require_permission(Permission.HIRING_REQUEST_VIEW))],
)

ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".csv"}


@router.post("/{hiring_request_id}/candidates/import", response_model=ImportCandidatesResponse)
def import_candidates(
    hiring_request_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    filename = (file.filename or "").lower()
    ext = None
    for allowed in ALLOWED_EXTENSIONS:
        if filename.endswith(allowed):
            ext = allowed
            break

    if not ext:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    result = CandidateImportService(db).import_from_file(
        hiring_request_id=str(hiring_request_id),
        filename=file.filename or "import.csv",
        file=file.file,
    )

    if result.errors and result.created == 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=result.errors)

    return result

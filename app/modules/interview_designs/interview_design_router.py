from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.authorization import require_permission
from app.core.permissions import Permission
from app.db.session import get_db
from app.modules.interview_designs.interview_design_schema import (
    InterviewDesignGenerate,
    InterviewDesignResponse,
    InterviewDesignUpdate,
)
from app.modules.interview_designs.interview_design_service import (
    generate_design,
    get_or_seed_design,
    update_design,
)
from app.modules.interview_designs.pdf import InterviewDesignPdfExportService
from app.modules.interview_designs.pdf.kinds import ExportKind

router = APIRouter(
    prefix="/api/v1/hiring-requests/{hiring_request_id}/ai",
    tags=["interview-design"],
    dependencies=[Depends(require_permission(Permission.APPLICATION_VIEW))],
)


@router.get("/questions", response_model=InterviewDesignResponse)
async def get_questions(
    hiring_request_id: str,
    db: Session = Depends(get_db),
):
    return await get_or_seed_design(hiring_request_id, db)


@router.get("/questions/export")
def export_interview_design_pdf(
    hiring_request_id: str,
    db: Session = Depends(get_db),
    kind: ExportKind = Query(default="all"),
):
    buf, filename = InterviewDesignPdfExportService(db).export(hiring_request_id, kind=kind)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.put(
    "/questions",
    response_model=InterviewDesignResponse,
    dependencies=[Depends(require_permission(Permission.INTERVIEW_PLAN_EDIT))],
)
async def update_questions(
    hiring_request_id: str,
    body: InterviewDesignUpdate,
    db: Session = Depends(get_db),
):
    return await update_design(hiring_request_id, body, db)


@router.post(
    "/questions/generate",
    response_model=InterviewDesignResponse,
    dependencies=[Depends(require_permission(Permission.INTERVIEW_PLAN_EDIT))],
)
async def generate_questions(
    hiring_request_id: str,
    body: InterviewDesignGenerate,
    db: Session = Depends(get_db),
):
    """Generate screening or interview questions via the AI service, store them, and sync to ai-recruitment-poc."""
    return await generate_design(hiring_request_id, body, db)

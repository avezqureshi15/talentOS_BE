from __future__ import annotations

import io
import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.common.pdf import PdfService
from app.modules.hiring_requests.hiring_request_model import HiringRequest
from app.modules.interview_designs.interview_design_model import InterviewDesign
from app.modules.interview_designs.pdf.kinds import ExportKind
from app.modules.interview_designs.pdf.mappers import build_document_spec, safe_filename


class InterviewDesignPdfExportService:
    """Load interview design data and render via the shared PdfService (no ReportLab here)."""

    def __init__(self, db: Session, pdf_service: PdfService | None = None):
        self.db = db
        self.pdf = pdf_service or PdfService()

    def export(
        self,
        hiring_request_id: str | uuid.UUID,
        kind: ExportKind = "all",
    ) -> tuple[io.BytesIO, str]:
        try:
            hr_id = hiring_request_id if isinstance(hiring_request_id, uuid.UUID) else uuid.UUID(str(hiring_request_id))
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=404, detail="Hiring request not found") from exc

        hiring_request = self.db.query(HiringRequest).filter(HiringRequest.id == hr_id).first()
        if not hiring_request:
            raise HTTPException(status_code=404, detail="Hiring request not found")

        design = (
            self.db.query(InterviewDesign)
            .filter(InterviewDesign.hiring_request_id == hiring_request.id)
            .first()
        )
        if not design:
            raise HTTPException(status_code=404, detail="Interview design not found")

        spec = build_document_spec(hiring_request, design, kind=kind)
        buf = self.pdf.render(spec)
        return buf, safe_filename(str(hiring_request.title or "export"), kind)

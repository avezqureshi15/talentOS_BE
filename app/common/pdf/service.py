from __future__ import annotations

import io

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate

from app.common.pdf.builders import build_document_flowables
from app.common.pdf.models import DocumentSpec
from app.common.pdf.styles import BRAND_NAME, COLOR_MUTED, PAGE_MARGIN


class PdfService:
    """Reusable PDF renderer. Domain modules pass a DocumentSpec; they never touch ReportLab."""

    def render(self, spec: DocumentSpec) -> io.BytesIO:
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=PAGE_MARGIN,
            rightMargin=PAGE_MARGIN,
            topMargin=PAGE_MARGIN,
            bottomMargin=PAGE_MARGIN,
            title=spec.title or BRAND_NAME,
            author=BRAND_NAME,
        )
        flowables = build_document_flowables(spec)

        def _on_page(canvas, document):
            canvas.saveState()
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(COLOR_MUTED)
            canvas.drawString(PAGE_MARGIN, 0.45 * 72, BRAND_NAME)
            canvas.drawRightString(
                A4[0] - PAGE_MARGIN,
                0.45 * 72,
                f"Page {document.page}",
            )
            canvas.restoreState()

        doc.build(flowables, onFirstPage=_on_page, onLaterPages=_on_page)
        buf.seek(0)
        return buf

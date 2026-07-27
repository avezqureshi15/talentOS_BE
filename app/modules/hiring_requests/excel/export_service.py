import io
from collections import defaultdict
from uuid import UUID

from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.modules.applications.application_repository import ApplicationRepository
from app.modules.evaluations.evaluation_model import Candidate
from app.modules.hiring_requests.excel.builders import (
    build_candidates_sheet,
    build_hiring_request_sheet,
)
from app.modules.hiring_requests.excel.stage_config import (
    ALL_CANDIDATES_SHEET_TITLE,
    STAGE_SHEETS,
    resolve_stage_sheet_key,
)
from app.modules.hiring_requests.hiring_request_service import HiringRequestService

logger = get_logger(__name__)


class HiringRequestExportService:
    """Build a multi-sheet Excel export for a hiring request and its candidates."""

    def __init__(self, db: Session):
        self.db = db
        self.hiring_requests = HiringRequestService(db)
        self.applications = ApplicationRepository(db)

    def export(self, hiring_request_id: UUID) -> tuple[io.BytesIO, str]:
        job_data = self.hiring_requests.get_hiring_request_by_id(hiring_request_id)
        job = job_data["data"]
        external_job_id = job.get("external_job_id")

        candidates: list[Candidate] = []
        if external_job_id:
            candidates = self.applications.get_candidates_by_job(str(external_job_id))
        else:
            logger.warning(
                "Hiring request %s has no external_job_id — exporting empty candidate sheets",
                hiring_request_id,
            )

        disqualified_map = self.applications.build_disqualified_by_map(candidates)
        rows = [self._candidate_to_row(c, disqualified_map.get(c.id, [])) for c in candidates]

        grouped: dict[str, list[dict]] = defaultdict(list)
        for candidate, row in zip(candidates, rows, strict=True):
            grouped[resolve_stage_sheet_key(candidate)].append(row)

        buf = self._build_workbook(job, rows, grouped)
        safe_title = str(job.get("title") or "export").replace("/", "_").replace("\\", "_")
        filename = f"{safe_title}_applicants.xlsx"
        return buf, filename

    def _build_workbook(
        self,
        job: dict,
        all_rows: list[dict],
        grouped: dict[str, list[dict]],
    ) -> io.BytesIO:
        wb = Workbook()
        build_hiring_request_sheet(wb, job)
        build_candidates_sheet(wb, ALL_CANDIDATES_SHEET_TITLE, all_rows)

        for sheet in STAGE_SHEETS:
            build_candidates_sheet(wb, sheet.title, grouped.get(sheet.key, []))

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf

    @staticmethod
    def _candidate_to_row(candidate: Candidate, disqualified_by: list[str]) -> dict:
        return {
            "name": candidate.candidate_name or "",
            "email": candidate.candidate_email or "",
            "phone": candidate.candidate_phone or "",
            "status": candidate.status or "",
            "stage": candidate.stage or "",
            "fit_score": candidate.fit_score if candidate.fit_score is not None else "",
            "review_verdict": candidate.review_verdict or "",
            "final_verdict": candidate.final_verdict or "",
            "disqualified_by": ", ".join(disqualified_by),
            "current_ctc": candidate.current_ctc or "",
            "expected_ctc": candidate.expected_ctc or "",
            "years_of_experience": candidate.years_of_experience or "",
            "location": candidate.location or "",
            "notice_period": candidate.notice_period or "",
            "willing_to_relocate": "Yes" if candidate.willing_to_relocate else "No",
            "linkedin_url": candidate.linkedin_url or "",
            "resume_url": candidate.resume_url or "",
            "applied_at": candidate.created_at.isoformat() if candidate.created_at else "",
        }

import re
import uuid
from io import BytesIO
from uuid import UUID

from fastapi import HTTPException, UploadFile
from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.common.clients.supabase_client import SupabaseClient
from app.core.logger import get_logger
from app.modules.hiring_requests.excel.import_service import (
    MAX_LENGTHS,
    CandidateImportService,
)

logger = get_logger(__name__)

MAX_RESUME_BYTES = 2 * 1024 * 1024

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?:\+?\d[\d\s\-()]{8,}\d)")


def _clean_phone(value: str | None) -> str | None:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) > 10:
        digits = digits[-10:]
    return digits or None


def _truncate(value: str | None, limit: int) -> str | None:
    text = (value or "").strip()
    return text[:limit] or None


def _extract_text(content: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:  # noqa: BLE001 - malformed PDFs simply yield no parsed fields
        logger.warning("Resume PDF text extraction failed: %s", exc)
        return ""


def _guess_name(text: str) -> str:
    """Best-effort name from the resume header (first title-cased line without digits)."""
    for line in text.splitlines():
        candidate = line.strip()
        if not (2 <= len(candidate) <= 60):
            continue
        if "@" in candidate or any(ch.isdigit() for ch in candidate):
            continue
        words = candidate.split()
        if 1 < len(words) <= 5 and all(w[:1].isupper() for w in words):
            return candidate
    return ""


def _parse_resume_fields(content: bytes, name: str, email: str, phone: str) -> tuple[str, str, str]:
    """Fill any missing name/email/phone from the resume text (local, no AI call)."""
    if name and email and phone:
        return name, email, phone

    text = _extract_text(content)
    if not text.strip():
        return name, email, phone

    if not email:
        match = _EMAIL_RE.search(text)
        if match:
            email = match.group(0).strip()
    if not phone:
        match = _PHONE_RE.search(text)
        if match:
            phone = _clean_phone(match.group(0)) or phone
    if not name:
        name = _guess_name(text)
    return name, email, phone


class AddCandidateService:
    """Proxy the careers apply flow: upload the PDF to `resumes`, insert `job_applications`.

    Resume-only add: name/email/phone are derived from the PDF when not supplied.
    We only mirror what the public webknot apply form does (storage upload + insert
    with the publishable key) — the downstream `job_applications` webhook runs ATS
    parsing/evaluation. TalentOS does not call the AI service here.

    TalentOS does not persist the candidate — the existing INSERT webhook queues ATS.
    """

    def __init__(self, db: Session):
        self.db = db
        self.import_service = CandidateImportService(db)
        self.supabase = SupabaseClient()

    def add_candidate(
        self,
        hiring_request_id: UUID,
        *,
        name: str | None,
        email: str | None,
        phone: str | None,
        referral: bool,
        resume: UploadFile,
    ) -> dict:
        content = resume.file.read()
        pdf_error = self._validate_resume(resume, content)
        if pdf_error:
            raise HTTPException(status_code=400, detail={"errors": [pdf_error]})

        name, email, phone = _parse_resume_fields(
            content,
            (name or "").strip(),
            (email or "").strip(),
            _clean_phone(phone) or "",
        )

        external_job_id = self.import_service._resolve_external_job_id(hiring_request_id)

        object_name = f"{uuid.uuid4()}.pdf"
        resume_url = self.supabase.upload_resume(object_name, content)
        row = self.supabase.create_job_application(
            {
                "job_id": external_job_id,
                "name": _truncate(name, MAX_LENGTHS["name"]),
                "email": _truncate(email, MAX_LENGTHS["email"]),
                "phone": _truncate(phone, MAX_LENGTHS["phone"]),
                "resume_url": resume_url,
                "candidate_type": "REFERRAL" if referral else "REGULAR",
                "cover_letter": None,
                "linkedin_url": None,
            }
        )
        application_id = str(row.get("id") or "")
        logger.info(
            "Add candidate submitted: hiring_request=%s | job_applications.id=%s",
            hiring_request_id,
            application_id or "(returned none)",
        )
        return {"id": application_id, "status": "queued"}

    @staticmethod
    def _validate_resume(resume: UploadFile, content: bytes) -> str | None:
        filename = (resume.filename or "").lower()
        content_type = (resume.content_type or "").split(";")[0].strip().lower()
        is_pdf = filename.endswith(".pdf") or content_type == "application/pdf"
        if not is_pdf:
            return "Resume must be a PDF"
        if not content:
            return "Resume file is empty"
        if len(content) > MAX_RESUME_BYTES:
            return "Resume must be 2MB or smaller"
        return None

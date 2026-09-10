import re
import uuid
from uuid import UUID

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.common.clients.supabase_client import SupabaseClient
from app.core.logger import get_logger
from app.modules.hiring_requests.excel.import_service import (
    EMAIL_RE,
    MAX_LENGTHS,
    CandidateImportService,
)

logger = get_logger(__name__)

MAX_RESUME_BYTES = 2 * 1024 * 1024


def _is_valid_phone(value: str) -> bool:
    digits = re.sub(r"[\s\-()]", "", value.strip())
    return bool(re.fullmatch(r"[6-9]\d{9}", digits))


class AddCandidateService:
    """Proxy the careers apply flow: upload PDF to `resumes`, insert `job_applications`.

    TalentOS does not persist the candidate here — the existing INSERT webhook queues ATS.
    """

    def __init__(self, db: Session):
        self.db = db
        self.import_service = CandidateImportService(db)
        self.supabase = SupabaseClient()

    def add_candidate(
        self,
        hiring_request_id: UUID,
        *,
        name: str,
        email: str,
        phone: str,
        referral: bool,
        resume: UploadFile,
    ) -> dict:
        errors = self._validate_fields(name, email, phone)
        if errors:
            raise HTTPException(status_code=400, detail={"errors": errors})

        content = resume.file.read()
        pdf_error = self._validate_resume(resume, content)
        if pdf_error:
            raise HTTPException(status_code=400, detail={"errors": [pdf_error]})

        external_job_id = self.import_service._resolve_external_job_id(hiring_request_id)

        object_name = f"{uuid.uuid4()}.pdf"
        resume_url = self.supabase.upload_resume(object_name, content)
        row = self.supabase.create_job_application(
            {
                "job_id": external_job_id,
                "name": name.strip()[: MAX_LENGTHS["name"]],
                "email": email.strip()[: MAX_LENGTHS["email"]],
                "phone": phone.strip()[: MAX_LENGTHS["phone"]],
                "resume_url": resume_url,
                "candidate_type": "REFERRAL" if referral else "REGULAR",
                "cover_letter": None,
                "linkedin_url": None,
            }
        )
        application_id = str(row["id"])
        logger.info(
            "Add candidate submitted: hiring_request=%s | job_applications.id=%s",
            hiring_request_id,
            application_id,
        )
        return {"id": application_id, "status": "queued"}

    @staticmethod
    def _validate_fields(name: str, email: str, phone: str) -> list[str]:
        errors: list[str] = []
        if not (name or "").strip():
            errors.append("Name is required")
        email_value = (email or "").strip()
        if not email_value:
            errors.append("Email is required")
        elif not EMAIL_RE.match(email_value):
            errors.append("Email is invalid")
        phone_value = (phone or "").strip()
        if not phone_value:
            errors.append("Phone is required")
        elif not _is_valid_phone(phone_value):
            errors.append("Phone must be a 10-digit number starting with 6, 7, 8, or 9")
        return errors

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

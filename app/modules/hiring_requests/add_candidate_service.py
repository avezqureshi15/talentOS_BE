import re
import uuid
from io import BytesIO
from uuid import UUID

from fastapi import HTTPException, UploadFile
from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.common.clients import AIClient, AIClientError
from app.common.clients.supabase_client import SupabaseClient
from app.core.logger import get_logger
from app.modules.hiring_requests.excel.import_service import (
    MAX_LENGTHS,
    CandidateImportService,
)

logger = get_logger(__name__)

MAX_RESUME_BYTES = 2 * 1024 * 1024
MAX_RESUME_PARSE_CHARS = 20_000
MAX_RESUME_PARSE_PAGES = 5

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?:\+?\d[\d\s\-()]{8,}\d)")
_LINKEDIN_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w\-/%]+", re.I)

_RESUME_PARSE_PROMPT = """\
Extract the candidate's contact details from the resume text.

Rules:
- Use only information present in the resume. Never invent values.
- If a field is missing, return an empty string.
- name: the candidate's full name (not a company, university, or section heading).
- email: the candidate's personal or professional email address.
- phone: the candidate's phone number as written.
- linkedin_url: a LinkedIn profile URL if present (prefer https://linkedin.com/in/...).
"""

_RESUME_PARSE_SCHEMA: dict = {
    "title": "ParsedResume",
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "email": {"type": "string"},
        "phone": {"type": "string"},
        "linkedin_url": {"type": "string"},
    },
    "required": ["name", "email", "phone", "linkedin_url"],
}


def _clean_phone(value: str | None) -> str | None:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) > 10:
        digits = digits[-10:]
    return digits or None


def _truncate(value: str | None, limit: int) -> str | None:
    text = (value or "").strip()
    return text[:limit] or None


def _as_str(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_linkedin(value: str | None) -> str:
    url = (value or "").strip()
    if not url:
        return ""
    if not re.search(r"linkedin\.com/in/", url, re.I):
        return ""
    if not url.lower().startswith("http"):
        url = "https://" + url.lstrip("/")
    return url


def _cap_resume_text(text: str) -> str:
    if len(text) <= MAX_RESUME_PARSE_CHARS:
        return text
    logger.info(
        "Resume text truncated from %s to %s chars before parse",
        len(text),
        MAX_RESUME_PARSE_CHARS,
    )
    return text[:MAX_RESUME_PARSE_CHARS]


def _extract_text(content: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(content))
        pages = reader.pages[:MAX_RESUME_PARSE_PAGES]
        text = "\n".join(page.extract_text() or "" for page in pages)
    except Exception as exc:  # noqa: BLE001 - malformed PDFs simply yield no parsed fields
        logger.warning("Resume PDF text extraction failed: %s", exc)
        return ""
    return _cap_resume_text(text)


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


def _regex_parse_resume(text: str) -> dict[str, str]:
    email = ""
    phone = ""
    linkedin_url = ""
    match = _EMAIL_RE.search(text)
    if match:
        email = match.group(0).strip()
    match = _PHONE_RE.search(text)
    if match:
        phone = _clean_phone(match.group(0)) or ""
    match = _LINKEDIN_RE.search(text)
    if match:
        linkedin_url = _normalize_linkedin(match.group(0))
    return {
        "name": _guess_name(text),
        "email": email,
        "phone": phone,
        "linkedin_url": linkedin_url,
    }


def _parse_resume_with_ai(text: str) -> dict[str, str]:
    try:
        response = AIClient().generate(
            prompt=_RESUME_PARSE_PROMPT,
            input_data={"resume_text": text},
            response_schema=_RESUME_PARSE_SCHEMA,
        )
    except AIClientError as exc:
        logger.warning("AI resume parse failed: %s", exc)
        return {}

    result = response.result if isinstance(response.result, dict) else {}
    return {
        "name": _as_str(result.get("name")),
        "email": _as_str(result.get("email")),
        "phone": _as_str(result.get("phone")),
        "linkedin_url": _normalize_linkedin(_as_str(result.get("linkedin_url"))),
    }


def _fill_missing(current: str, *candidates: str) -> str:
    if current:
        return current
    for value in candidates:
        if value:
            return value
    return current


def _parse_resume_fields(
    content: bytes,
    name: str,
    email: str,
    phone: str,
    linkedin_url: str = "",
) -> tuple[str, str, str, str]:
    """Fill missing name/email/phone/linkedin from the resume (AI, then regex fallback)."""
    if name and email and phone and linkedin_url:
        return name, email, phone, linkedin_url

    text = _extract_text(content)
    if not text.strip():
        return name, email, phone, linkedin_url

    ai_fields = _parse_resume_with_ai(text)
    regex_fields = _regex_parse_resume(text)

    name = _fill_missing(name, ai_fields.get("name", ""), regex_fields["name"])
    email = _fill_missing(email, ai_fields.get("email", ""), regex_fields["email"])
    phone = _fill_missing(
        phone,
        _clean_phone(ai_fields.get("phone")) or "",
        regex_fields["phone"],
    )
    linkedin_url = _fill_missing(
        linkedin_url,
        ai_fields.get("linkedin_url", ""),
        regex_fields["linkedin_url"],
    )
    return name, email, phone, linkedin_url


class AddCandidateService:
    """Proxy the careers apply flow: upload the PDF to `resumes`, insert `job_applications`.

    Resume-only add: name/email/phone/linkedin are derived from the PDF when not
    supplied (AI structured generate, regex fallback). We only mirror what the
    public webknot apply form does (storage upload + insert) — the downstream
    `job_applications` webhook still runs ATS evaluation.

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

        name, email, phone, linkedin_url = _parse_resume_fields(
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
                "linkedin_url": _truncate(linkedin_url, MAX_LENGTHS["linkedin_url"]),
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

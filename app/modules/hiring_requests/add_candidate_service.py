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
MAX_RESUME_PARSE_CHARS = 40_000

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?:\+?\d[\d\s\-()]{8,}\d)")
_LINKEDIN_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w\-/%]+", re.I)
_NUMBER_RE = re.compile(r"(\d+(?:\.\d+)?)")
_TRUE_VALUES = {"true", "yes", "1", "y"}

_STRING_FIELDS = (
    "name",
    "email",
    "phone",
    "linkedin_url",
    "location",
    "current_ctc",
    "expected_ctc",
    "years_of_experience",
    "notice_period",
)

_RESUME_PARSE_PROMPT = """\
Extract the candidate's profile from the full resume text.

Rules:
- Use only information present in the resume. Never invent values.
- If a string field is missing or unclear, return an empty string.
- willing_to_relocate must be false unless the resume clearly says they will relocate.
- name: the candidate's full name (not a company, university, or section heading).
- email: the candidate's personal or professional email address.
- phone: the candidate's phone number as written.
- linkedin_url: a LinkedIn profile URL if present (prefer https://linkedin.com/in/...).
- location: current city / location (e.g. "Bengaluru, India").
- current_ctc: current compensation as a number in LPA only (e.g. "18"). No currency words.
- expected_ctc: expected compensation as a number in LPA only (e.g. "22"). No currency words.
- years_of_experience: total professional experience as a number of years (e.g. "5" or "8.5").
- notice_period: notice in days as a number (e.g. "30"), or "immediate" if available immediately.
"""

_RESUME_PARSE_SCHEMA: dict = {
    "title": "ParsedResume",
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "email": {"type": "string"},
        "phone": {"type": "string"},
        "linkedin_url": {"type": "string"},
        "location": {"type": "string"},
        "current_ctc": {"type": "string"},
        "expected_ctc": {"type": "string"},
        "years_of_experience": {"type": "string"},
        "notice_period": {"type": "string"},
        "willing_to_relocate": {"type": "boolean"},
    },
    "required": [
        "name",
        "email",
        "phone",
        "linkedin_url",
        "location",
        "current_ctc",
        "expected_ctc",
        "years_of_experience",
        "notice_period",
        "willing_to_relocate",
    ],
}


def _empty_parsed() -> dict:
    fields: dict = {key: "" for key in _STRING_FIELDS}
    fields["willing_to_relocate"] = False
    return fields


def _clean_phone(value: str | None) -> str | None:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) > 10:
        digits = digits[-10:]
    return digits or None


def _truncate(value: str | None, limit: int | None) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    if limit is None:
        return text
    return text[:limit] or None


def _as_str(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return ""
    return str(value).strip()


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in _TRUE_VALUES


def _normalize_linkedin(value: str | None) -> str:
    url = (value or "").strip()
    if not url:
        return ""
    if not re.search(r"linkedin\.com/in/", url, re.I):
        return ""
    if not url.lower().startswith("http"):
        url = "https://" + url.lstrip("/")
    return url


def _first_number(value: str) -> str:
    match = _NUMBER_RE.search((value or "").replace(",", ""))
    return match.group(1) if match else ""


def _normalize_amount(value: object) -> str:
    """Keep a compact number so the UI can append LPA / yrs."""
    return _first_number(_as_str(value))


def _normalize_notice(value: object) -> str:
    text = _as_str(value)
    if not text:
        return ""
    if re.search(r"immediate|serving notice|available now", text, re.I):
        return "immediate"
    return _first_number(text)


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
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
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


def _regex_parse_resume(text: str) -> dict:
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
    fields = _empty_parsed()
    fields.update(
        {
            "name": _guess_name(text),
            "email": email,
            "phone": phone,
            "linkedin_url": linkedin_url,
        }
    )
    return fields


def _parse_resume_with_ai(text: str) -> dict:
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
        "location": _as_str(result.get("location")),
        "current_ctc": _normalize_amount(result.get("current_ctc")),
        "expected_ctc": _normalize_amount(result.get("expected_ctc")),
        "years_of_experience": _normalize_amount(result.get("years_of_experience")),
        "notice_period": _normalize_notice(result.get("notice_period")),
        "willing_to_relocate": _as_bool(result.get("willing_to_relocate")),
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
) -> dict:
    """Fill candidate profile fields from the full resume (AI, then regex for contact)."""
    fields = _empty_parsed()
    fields["name"] = name
    fields["email"] = email
    fields["phone"] = phone
    fields["linkedin_url"] = linkedin_url

    text = _extract_text(content)
    if not text.strip():
        return fields

    ai_fields = _parse_resume_with_ai(text)
    regex_fields = _regex_parse_resume(text)

    fields["name"] = _fill_missing(name, ai_fields.get("name", ""), regex_fields["name"])
    fields["email"] = _fill_missing(email, ai_fields.get("email", ""), regex_fields["email"])
    fields["phone"] = _fill_missing(
        phone,
        _clean_phone(ai_fields.get("phone")) or "",
        regex_fields["phone"],
    )
    fields["linkedin_url"] = _fill_missing(
        linkedin_url,
        ai_fields.get("linkedin_url", ""),
        regex_fields["linkedin_url"],
    )
    fields["location"] = _as_str(ai_fields.get("location"))
    fields["current_ctc"] = _as_str(ai_fields.get("current_ctc"))
    fields["expected_ctc"] = _as_str(ai_fields.get("expected_ctc"))
    fields["years_of_experience"] = _as_str(ai_fields.get("years_of_experience"))
    fields["notice_period"] = _as_str(ai_fields.get("notice_period"))
    fields["willing_to_relocate"] = _as_bool(ai_fields.get("willing_to_relocate"))
    return fields


class AddCandidateService:
    """Proxy the careers apply flow: upload the PDF to `resumes`, insert `job_applications`.

    Resume-only add: the full PDF text is sent to AI to fill profile fields
    (contact, location, CTC, YOE, notice, relocate). Regex fills name/email/phone/
    linkedin if AI is unavailable. The downstream `job_applications` webhook still
    runs ATS evaluation.

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

        parsed = _parse_resume_fields(
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
                "name": _truncate(parsed["name"], MAX_LENGTHS["name"]),
                "email": _truncate(parsed["email"], MAX_LENGTHS["email"]),
                "phone": _truncate(parsed["phone"], MAX_LENGTHS["phone"]),
                "resume_url": resume_url,
                "candidate_type": "REFERRAL" if referral else "REGULAR",
                "cover_letter": None,
                "linkedin_url": _truncate(parsed["linkedin_url"], MAX_LENGTHS["linkedin_url"]),
                "location": _truncate(parsed["location"], MAX_LENGTHS["location"]),
                "current_ctc": _truncate(parsed["current_ctc"], MAX_LENGTHS["current_ctc"]),
                "expected_ctc": _truncate(parsed["expected_ctc"], MAX_LENGTHS["expected_ctc"]),
                "years_of_experience": _truncate(
                    parsed["years_of_experience"], MAX_LENGTHS["years_of_experience"]
                ),
                "notice_period": _truncate(parsed["notice_period"], MAX_LENGTHS["notice_period"]),
                "willing_to_relocate": bool(parsed["willing_to_relocate"]),
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

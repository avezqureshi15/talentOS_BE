"""Parse an uploaded JD PDF into hiring-request create fields via AI generate."""

from __future__ import annotations

import re
from io import BytesIO
from typing import Any

from fastapi import HTTPException, UploadFile
from pypdf import PdfReader

from app.common.clients import AIClient, AIClientError
from app.core.logger import get_logger
from app.modules.hiring_requests.hiring_request_schema import ParsedHiringRequestJd

logger = get_logger(__name__)

MAX_JD_BYTES = 2 * 1024 * 1024
MAX_JD_PARSE_CHARS = 20_000
MAX_JD_PARSE_PAGES = 5

_JOB_TYPES = ("Full-time", "Part-time", "Contract", "Internship", "Freelance")
_JOB_TYPE_LOOKUP = {re.sub(r"[\s\-]+", "", t.lower()): t for t in _JOB_TYPES}

_JD_PARSE_PROMPT = """\
Extract a hiring request from the job description text.

Rules:
- Use only information present in the document. Never invent values.
- If a field is missing, return an empty string or empty array.
- title: the job title only (not a company name or document heading like "Job Description").
- department: team or function (e.g. Engineering, HR). Empty if not stated.
- type: one of Full-time, Part-time, Contract, Internship, Freelance. Empty if not stated.
- location: list of work locations (city names or Remote). Empty array if not stated.
- description: the role overview / responsibilities as readable prose.
- requirements: distinct requirement bullets. Empty array if none.
- benefits: distinct benefit bullets. Empty array if none.
- custom_evaluation_criteria: screening or must-have criteria for resume evaluation. Empty if none.
"""

_JD_PARSE_SCHEMA: dict = {
    "title": "ParsedHiringRequest",
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "department": {"type": "string"},
        "type": {"type": "string"},
        "location": {"type": "array", "items": {"type": "string"}},
        "description": {"type": "string"},
        "requirements": {"type": "array", "items": {"type": "string"}},
        "benefits": {"type": "array", "items": {"type": "string"}},
        "custom_evaluation_criteria": {"type": "string"},
    },
    "required": [
        "title",
        "department",
        "type",
        "location",
        "description",
        "requirements",
        "benefits",
        "custom_evaluation_criteria",
    ],
}


def _as_str(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_str_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [line.strip() for line in value.splitlines() if line.strip()]
    return []


def _truncate(value: str, limit: int) -> str:
    return value[:limit] if len(value) > limit else value


def _normalize_type(value: str) -> str:
    compact = re.sub(r"[\s\-]+", "", value.strip().lower())
    return _JOB_TYPE_LOOKUP.get(compact, "")


def _cap_jd_text(text: str) -> str:
    if len(text) <= MAX_JD_PARSE_CHARS:
        return text
    logger.info("JD text truncated from %s to %s chars before parse", len(text), MAX_JD_PARSE_CHARS)
    return text[:MAX_JD_PARSE_CHARS]


def _extract_text(content: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(content))
        pages = reader.pages[:MAX_JD_PARSE_PAGES]
        text = "\n".join(page.extract_text() or "" for page in pages)
    except Exception as exc:  # noqa: BLE001
        logger.warning("JD PDF text extraction failed: %s", exc)
        return ""
    return _cap_jd_text(text)


def _validate_pdf(file: UploadFile, content: bytes) -> str | None:
    filename = (file.filename or "").lower()
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    is_pdf = filename.endswith(".pdf") or content_type == "application/pdf"
    if not is_pdf:
        return "Job description must be a PDF"
    if not content:
        return "Job description file is empty"
    if len(content) > MAX_JD_BYTES:
        return "Job description must be 2MB or smaller"
    return None


def _to_parsed(result: dict[str, Any]) -> ParsedHiringRequestJd:
    locations = [_truncate(item, 255) for item in _as_str_list(result.get("location"))]
    return ParsedHiringRequestJd(
        title=_truncate(_as_str(result.get("title")), 255),
        department=_truncate(_as_str(result.get("department")), 255),
        type=_normalize_type(_as_str(result.get("type"))),
        location=locations,
        description=_as_str(result.get("description")),
        requirements=_as_str_list(result.get("requirements")),
        benefits=_as_str_list(result.get("benefits")),
        custom_evaluation_criteria=_as_str(result.get("custom_evaluation_criteria")),
    )


def parse_jd_file(file: UploadFile) -> ParsedHiringRequestJd:
    content = file.file.read()
    error = _validate_pdf(file, content)
    if error:
        raise HTTPException(status_code=400, detail=error)

    text = _extract_text(content)
    if not text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from this PDF")

    try:
        response = AIClient().generate(
            prompt=_JD_PARSE_PROMPT,
            input_data={"job_description_text": text},
            response_schema=_JD_PARSE_SCHEMA,
        )
    except AIClientError as exc:
        logger.warning("AI JD parse failed: %s", exc)
        raise HTTPException(
            status_code=exc.status_code or 502,
            detail=exc.message or "Failed to parse job description",
        ) from exc

    result = response.result if isinstance(response.result, dict) else {}
    parsed = _to_parsed(result)
    if not parsed.title and not parsed.description:
        raise HTTPException(status_code=502, detail="AI parse returned no job details — try another file")
    return parsed

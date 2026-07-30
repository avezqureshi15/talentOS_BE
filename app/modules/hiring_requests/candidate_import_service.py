import csv
import io
import re
import uuid
from typing import BinaryIO

import openpyxl

from sqlalchemy import exists
from sqlalchemy.orm import Session

from app.core.constants import EvaluationStatus
from app.modules.evaluations.evaluation_model import Candidate
from app.modules.hiring_requests.candidate_import_schema import ImportCandidatesResponse


MAX_ROWS = 50

_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

_COL_ALIASES: dict[str, list[str]] = {
    "name": ["name", "full_name", "fullname", "candidate_name", "candidate name"],
    "email": ["email", "email_address", "emailaddress", "e-mail", "candidate_email", "candidate email"],
    "phone": ["phone", "phone_number", "phonenumber", "mobile", "telephone", "contact", "candidate_phone", "candidate phone"],
    "resume_url": ["resume_url", "resume", "resume_link", "cv", "cv_url", "cv_link", "url", "resume url", "cv url", "resume_link", "cv_link"],
}


def _pick(normalized: dict[str, str], field: str) -> str:
    for alias in _COL_ALIASES.get(field, []):
        val = normalized.get(alias)
        if val is not None:
            return str(val)
    return ""


class CandidateImportService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def import_from_file(self, hiring_request_id: str, filename: str, file: BinaryIO) -> ImportCandidatesResponse:
        rows = self._parse_file(filename, file)
        return self._process_rows(hiring_request_id, rows)

    def _parse_file(self, filename: str, file: BinaryIO) -> list[dict]:
        ext = filename.lower()
        if ext.endswith(".csv"):
            return self._parse_csv(file)
        return self._parse_xlsx(file)

    def _parse_csv(self, file: BinaryIO) -> list[dict]:
        text = io.StringIO(file.read().decode("utf-8-sig"))
        reader = csv.DictReader(text)
        rows = []
        for row in reader:
            normalized = {k.lower().strip(): v for k, v in row.items()}
            rows.append({
                "name": _pick(normalized, "name").strip(),
                "email": _pick(normalized, "email").strip(),
                "phone": _pick(normalized, "phone").strip(),
                "resume_url": _pick(normalized, "resume_url").strip(),
            })
        return rows

    def _parse_xlsx(self, file: BinaryIO) -> list[dict]:
        wb = openpyxl.load_workbook(file, read_only=True, data_only=True)
        ws = wb.active
        rows_iter = ws.iter_rows(values_only=True)
        header = [str(c).strip().lower() if c else "" for c in next(rows_iter, [])]
        rows = []
        for row in rows_iter:
            if not any(row):
                continue
            row_dict = {header[i]: str(row[i] or "").strip() for i in range(len(header)) if i < len(row)}
            rows.append({
                "name": _pick(row_dict, "name"),
                "email": _pick(row_dict, "email"),
                "phone": _pick(row_dict, "phone"),
                "resume_url": _pick(row_dict, "resume_url"),
            })
        wb.close()
        return rows

    def _process_rows(self, hiring_request_id: str, rows: list[dict]) -> ImportCandidatesResponse:
        result = ImportCandidatesResponse(total=len(rows))

        if not rows:
            return result

        if len(rows) > MAX_ROWS:
            result.errors.append({"row": 0, "reason": f"Maximum {MAX_ROWS} candidates allowed per import, got {len(rows)}"})
            return result

        for idx, row in enumerate(rows):
            row_num = idx + 2

            name = (row.get("name") or "").strip()
            email = (row.get("email") or "").strip()
            phone = (row.get("phone") or "").strip() or None
            resume_url = (row.get("resume_url") or "").strip()

            errors = []
            if not name:
                errors.append("name is required")
            if not email:
                errors.append("email is required")
            elif not _EMAIL_PATTERN.match(email):
                errors.append("invalid email format")
            if not resume_url:
                errors.append("resume_url is required")
            elif not resume_url.startswith(("http://", "https://")):
                errors.append("resume_url must be a valid URL")

            if errors:
                result.errors.append({"row": row_num, "reason": "; ".join(errors)})
                continue

            exists_q = self._db.query(exists().where(
                Candidate.external_job_id == hiring_request_id,
                Candidate.candidate_email == email,
            )).scalar()
            if exists_q:
                result.skipped += 1
                result.errors.append({"row": row_num, "reason": f"Duplicate email: {email}"})
                continue

            candidate = Candidate(
                external_application_id=f"import-{uuid.uuid4()}",
                external_job_id=hiring_request_id,
                candidate_name=name,
                candidate_email=email,
                candidate_phone=phone,
                resume_url=resume_url,
                candidate_type="REGULAR",
                status=EvaluationStatus.QUEUED.value,
            )
            self._db.add(candidate)
            result.created += 1

        self._db.commit()
        return result

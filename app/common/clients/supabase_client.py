from uuid import UUID

import httpx

from app.common.clients.base_client import BaseClient, ClientError
from app.core.config import settings
from app.core.constants import ErrorCode
from app.core.logger import get_logger
from app.core.secrets import get_secret

_RESUME_BUCKET = "resumes"

logger = get_logger(__name__)


class SupabaseClient(BaseClient):
    """Client for Supabase Edge Functions.

    Endpoints
    ---------
    - ``manage-job-listings`` — CRUD for job postings
    - ``get-applications`` — fetch submitted applications
    - ``send-application-email`` — send confirmation emails
    """

    def __init__(self) -> None:
        super().__init__(
            base_url=settings.SUPABASE_FUNCTIONS_BASE_URL,
            timeout=30,
            max_retries=2,
        )

    @property
    def _service_name(self) -> str:
        return "Supabase"

    # ── job listings ─────────────────────────────────────────────

    def get_all_jobs(self) -> dict:
        logger.info("Fetching all job listings from Supabase")
        return self._get("manage-job-listings").json()

    def get_job_by_id(self, job_id: UUID) -> dict:
        return self._get("manage-job-listings", params={"id": str(job_id)}).json()

    def create_job(self, data: dict) -> dict:
        return self._post("manage-job-listings", json_data=data).json()

    def update_job(self, job_id: UUID, data: dict) -> dict:
        return self._put("manage-job-listings", params={"id": str(job_id)}, json_data=data).json()

    def delete_job(self, job_id: UUID) -> dict:
        return self._delete("manage-job-listings", params={"id": str(job_id)}).json()

    def fetch_jd_details(self, job_id: str) -> str:
        """Fetch job description and format as a text block for AI evaluation."""
        body = self._get("manage-job-listings", params={"id": job_id}).json()
        data = body.get("data", body) if isinstance(body, dict) else {}
        title = data.get("title", "")
        description = data.get("description", "")
        requirements = data.get("requirements") or []
        req_text = "\n".join(f"- {r}" for r in requirements) if isinstance(requirements, list) else str(requirements)
        return f"Title: {title}\n\nDescription:\n{description}\n\nRequirements:\n{req_text}".strip()

    def fetch_job_title(self, job_id: UUID) -> str:
        try:
            body = self._get("manage-job-listings", params={"id": str(job_id)}).json()
            return body.get("data", {}).get("title", "Job Listing")
        except ClientError:
            logger.warning("Could not fetch job title for job_id=%s", job_id)
            return "Job Listing"

    # ── applications ─────────────────────────────────────────────

    def get_applications(self) -> list[dict]:
        logger.info("Fetching applications from Supabase")
        raw = self._get("get-applications").json()
        if isinstance(raw, dict):
            return raw.get("data", raw.get("applications", []))
        if isinstance(raw, list):
            return raw
        return []

    def send_application_email(self, payload: dict) -> dict:
        logger.info("Sending application email via Supabase function")
        return self._post("send-application-email", json_data=payload).json()

    # ── careers apply (storage + REST) ─────────────────────────

    def _project_origin(self) -> str:
        base = (self._base_url or "").rstrip("/")
        if base.endswith("/functions/v1"):
            return base[: -len("/functions/v1")]
        if not base:
            raise ClientError(message="Resume storage is not configured", status_code=503)
        return base

    def _careers_auth_key(self) -> str:
        # Prefer the service-role key when configured; otherwise fall back to the
        # publishable (anon) key — exactly what the public webknot apply form uses.
        service_key = get_secret("SUPABASE_CAREERS_SERVICE_ROLE_KEY")
        if service_key:
            return service_key
        anon_key = get_secret("SUPABASE_CAREERS_ANON_KEY") or settings.SUPABASE_CAREERS_ANON_KEY
        if not anon_key:
            raise ClientError(message="Resume storage is not configured", status_code=503)
        return anon_key

    def _careers_service_role_headers(self) -> dict[str, str]:
        key = self._careers_auth_key()
        return {"Authorization": f"Bearer {key}", "apikey": key}

    def upload_resume(self, object_name: str, content: bytes) -> str:
        """Upload a PDF to the careers `resumes` bucket. Returns the public object URL."""
        origin = self._project_origin()
        url = f"{origin}/storage/v1/object/{_RESUME_BUCKET}/{object_name}"
        headers = {
            **self._careers_service_role_headers(),
            "Content-Type": "application/pdf",
            "cacheControl": "3600",
        }
        try:
            response = self.sync.post(url, content=content, headers=headers, timeout=60)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error("Resume upload failed: status=%s body=%s", exc.response.status_code, exc.response.text[:200])
            raise ClientError(message="Failed to upload resume", status_code=502) from exc
        except httpx.RequestError as exc:
            logger.error("Resume upload connection error: %s", exc)
            raise ClientError(message="Failed to upload resume", status_code=503) from exc
        return f"{origin}/storage/v1/object/public/{_RESUME_BUCKET}/{object_name}"

    def _careers_uses_service_role(self) -> bool:
        return bool(get_secret("SUPABASE_CAREERS_SERVICE_ROLE_KEY"))

    def create_job_application(self, payload: dict) -> dict:
        """Insert a row into `job_applications` (same as the careers apply form)."""
        origin = self._project_origin()
        url = f"{origin}/rest/v1/job_applications"
        wants_row = self._careers_uses_service_role()
        headers = {
            **self._careers_service_role_headers(),
            "Content-Type": "application/json",
            # The public apply form inserts with the anon key and does not read the
            # row back (RLS has no SELECT policy). Only ask for representation when
            # a service-role key is available.
            "Prefer": "return=representation" if wants_row else "return=minimal",
        }
        try:
            response = self.sync.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error("job_applications insert failed: status=%s body=%s", exc.response.status_code, exc.response.text[:200])
            raise ClientError(message="Failed to create application", status_code=502) from exc
        except httpx.RequestError as exc:
            logger.error("job_applications insert connection error: %s", exc)
            raise ClientError(message="Failed to create application", status_code=503) from exc

        if not response.content:
            return {}
        try:
            data = response.json()
        except ValueError:
            return {}
        row = data[0] if isinstance(data, list) and data else data
        return row if isinstance(row, dict) else {}

    # ── custom error mapping ─────────────────────────────────────

    def _map_error(self, exc: Exception) -> Exception:
        from httpx import HTTPStatusError

        if not isinstance(exc, HTTPStatusError):
            return super()._map_error(exc)

        status = exc.response.status_code
        body = self._try_extract_error(exc.response)
        if status == 404:
            from app.common.exceptions.job_exception import JobNotFoundException
            return JobNotFoundException()

        # Re-map common status codes
        code_map = {502: ErrorCode.EMAIL_SEND_FAILED}
        return ClientError(
            message=f"Supabase returned {status}: {body}",
            code=code_map.get(status, ErrorCode.INTERNAL_ERROR),
            status_code=status,
        )

    @staticmethod
    def _try_extract_error(response) -> str:
        try:
            data = response.json()
            return data.get("error", data.get("message", str(data)))
        except Exception:
            return response.text[:200]

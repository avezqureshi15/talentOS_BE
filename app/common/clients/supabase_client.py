from uuid import UUID

from app.common.clients.base_client import BaseClient, ClientError
from app.core.config import settings
from app.core.constants import ErrorCode
from app.core.logger import get_logger

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

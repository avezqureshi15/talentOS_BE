from uuid import UUID

import httpx

from app.common.exceptions.base_exception import BaseAppException
from app.core.config import settings
from app.core.constants import ErrorCode
from app.core.logger import get_logger
from app.modules.applications.application_schema import ApplicationCreate

logger = get_logger(__name__)

_APPLICATIONS_ENDPOINT: str = f"{settings.SUPABASE_FUNCTIONS_BASE_URL}/get-applications"
_JOBS_ENDPOINT: str = f"{settings.SUPABASE_FUNCTIONS_BASE_URL}/manage-job-listings"
_EMAIL_ENDPOINT: str = f"{settings.SUPABASE_FUNCTIONS_BASE_URL}/send-application-email"
_TIMEOUT: int = 30


class ApplicationService:
    def get_all_applications(self) -> dict:
        logger.info("Fetching all applications from Supabase")
        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                response = client.get(_APPLICATIONS_ENDPOINT)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            body = exc.response.json()
            error_msg = body.get("error", "Unknown error")
            logger.error("Supabase error: status=%d | error=%s", exc.response.status_code, error_msg)
            raise BaseAppException(
                message=error_msg,
                code=ErrorCode.INTERNAL_ERROR,
                status_code=exc.response.status_code,
            ) from exc
        except httpx.RequestError as exc:
            logger.error("Supabase connection error: %s", str(exc))
            raise BaseAppException(
                message="Failed to connect to applications service",
                code=ErrorCode.INTERNAL_ERROR,
                status_code=502,
            ) from exc

    def _fetch_job_title(self, job_id: UUID) -> str:
        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                response = client.get(_JOBS_ENDPOINT, params={"id": str(job_id)})
                response.raise_for_status()
                body = response.json()
                return body.get("data", {}).get("title", "Job Listing")
        except Exception as exc:
            logger.warning("Could not fetch job title for job_id=%s: %s", job_id, str(exc))
            return "Job Listing"

    def _to_camel_case(self, snake_data: dict) -> dict:
        mapping = {
            "job_id": "jobTitle",
            "cover_letter": "coverLetter",
            "resume_url": "resumeUrl",
        }
        camel = {}
        for key, value in snake_data.items():
            mapped = mapping.get(key, key)
            camel[mapped] = value
        return camel

    def create_application(self, data: ApplicationCreate) -> dict:
        logger.info("Creating application: job_id=%s | name=%s", data.job_id, data.name)

        job_title = self._fetch_job_title(data.job_id)

        payload = self._to_camel_case(data.model_dump())
        payload["jobTitle"] = job_title

        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                response = client.post(_EMAIL_ENDPOINT, json=payload)
                response.raise_for_status()
                email_result = response.json()
                logger.info("Application email sent: id=%s", email_result.get("id"))
                return {
                    "message": "Application submitted successfully",
                    "email_id": email_result.get("id"),
                }
        except httpx.HTTPStatusError as exc:
            body = exc.response.json()
            logger.error("Failed to send email: status=%d | error=%s", exc.response.status_code, body.get("error"))
            raise BaseAppException(
                message="Failed to send application email",
                code=ErrorCode.EMAIL_SEND_FAILED,
                status_code=502,
            ) from exc
        except httpx.RequestError as exc:
            logger.error("Email service unavailable: %s", str(exc))
            raise BaseAppException(
                message="Email service unavailable",
                code=ErrorCode.EMAIL_SEND_FAILED,
                status_code=502,
            ) from exc

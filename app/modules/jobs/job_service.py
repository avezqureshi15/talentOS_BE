import httpx

from app.common.exceptions.base_exception import BaseAppException
from app.common.exceptions.job_exception import JobNotFoundException
from app.core.config import settings
from app.core.constants import ErrorCode
from app.core.logger import get_logger
from app.modules.jobs.job_schema import JobCreate, JobUpdate

logger = get_logger(__name__)

_JOBS_ENDPOINT: str = f"{settings.SUPABASE_FUNCTIONS_BASE_URL}/manage-job-listings"
_TIMEOUT: int = 30


class JobService:
    def _request(self, method: str, params: dict | None = None, json_data: dict | None = None) -> dict:
        logger.info("Supabase request: method=%s | endpoint=manage-job-listings", method)
        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                response = client.request(method, _JOBS_ENDPOINT, params=params, json=json_data)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            body = exc.response.json()
            error_msg = body.get("error", "Unknown error")
            status_code = exc.response.status_code
            logger.error("Supabase error: status=%d | error=%s", status_code, error_msg)
            if status_code == 404:
                job_id = None
                if params and params.get("id"):
                    job_id = int(params["id"])
                raise JobNotFoundException(job_id) from exc
            raise BaseAppException(
                message=error_msg,
                code=ErrorCode.INTERNAL_ERROR,
                status_code=status_code,
            ) from exc
        except httpx.RequestError as exc:
            logger.error("Supabase connection error: %s", str(exc))
            raise BaseAppException(
                message="Failed to connect to job listings service",
                code=ErrorCode.INTERNAL_ERROR,
                status_code=502,
            ) from exc

    def get_all_jobs(self) -> dict:
        logger.info("Fetching all job listings from Supabase")
        return self._request("GET")

    def get_job_by_id(self, job_id: int) -> dict:
        logger.info("Fetching job listing: id=%d", job_id)
        return self._request("GET", params={"id": str(job_id)})

    def create_job(self, data: JobCreate) -> dict:
        logger.info("Creating job listing: title=%s", data.title)
        return self._request("POST", json_data=data.model_dump())

    def update_job(self, job_id: int, data: JobUpdate) -> dict:
        logger.info("Updating job listing: id=%d", job_id)
        payload = data.model_dump(exclude_unset=True)
        return self._request("PUT", params={"id": str(job_id)}, json_data=payload)

    def delete_job(self, job_id: int) -> dict:
        logger.info("Deleting job listing: id=%d", job_id)
        return self._request("DELETE", params={"id": str(job_id)})

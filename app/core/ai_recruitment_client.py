import logging
from typing import Any

import httpx

from app.core.secrets import get_secret
from app.core.service_token import create_service_token

logger = logging.getLogger(__name__)


class AiRecruitmentError(Exception):
    """Base error for ai-recruitment-poc client failures."""


class AiRecruitmentUnavailable(AiRecruitmentError):
    """Network/transport failure or the POC returned 5xx."""


class AiRecruitmentAuthError(AiRecruitmentError):
    """POC returned 401/403 — bad or missing API key."""


class AiRecruitmentNotFound(AiRecruitmentError):
    """POC returned 404 for the requested resource."""


class AiRecruitmentConflict(AiRecruitmentError):
    """POC returned 409 — the requested action conflicts with current state."""


class AiRecruitmentClient:
    def __init__(self) -> None:
        self.base_url = get_secret("RH_SERVICE_URL")

    def _headers(self) -> dict[str, str]:
        rh_api_key = get_secret("RH_API_KEY")
        if rh_api_key:
            return {"Authorization": f"Bearer {rh_api_key}"}
        return {"Authorization": f"Bearer {create_service_token()}"}

    async def _request(
        self,
        method: str,
        path: str,
        *,
        timeout: float,
        json: dict | None = None,
        params: dict | None = None,
        context: dict[str, Any] | None = None,
    ) -> Any:
        if not self.base_url:
            logger.warning("ai-recruitment-poc call skipped: RH_SERVICE_URL not set (path=%s)", path)
            raise AiRecruitmentUnavailable("RH_SERVICE_URL not configured")

        url = f"{self.base_url}{path}"
        ctx = context or {}
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.request(
                    method, url, json=json, params=params, headers=self._headers()
                )
        except httpx.HTTPError as exc:
            logger.error(
                "ai-recruitment-poc transport error method=%s path=%s ctx=%s err=%s",
                method, path, ctx, exc,
            )
            raise AiRecruitmentUnavailable(f"transport error: {exc}") from exc

        if resp.status_code in (401, 403):
            logger.error(
                "ai-recruitment-poc auth error method=%s path=%s ctx=%s status=%s body=%s",
                method, path, ctx, resp.status_code, resp.text[:500],
            )
            raise AiRecruitmentAuthError(f"auth failed (status={resp.status_code})")
        if resp.status_code == 404:
            logger.info(
                "ai-recruitment-poc not-found method=%s path=%s ctx=%s",
                method, path, ctx,
            )
            raise AiRecruitmentNotFound(f"not found: {path}")
        if resp.status_code == 409:
            logger.info(
                "ai-recruitment-poc conflict method=%s path=%s ctx=%s body=%s",
                method, path, ctx, resp.text[:300],
            )
            raise AiRecruitmentConflict(f"conflict: {path}")
        if resp.is_error:
            logger.error(
                "ai-recruitment-poc error method=%s path=%s ctx=%s status=%s body=%s",
                method, path, ctx, resp.status_code, resp.text[:500],
            )
            raise AiRecruitmentUnavailable(
                f"upstream error (status={resp.status_code})"
            )

        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    async def create_job(
        self,
        title: str,
        description: str,
        required_skills: list[str] | None = None,
        location: str | None = None,
        department: str | None = None,
        employment_type: str | None = None,
        external_job_id: str | None = None,
    ) -> dict | None:
        try:
            return await self._request(
                "POST",
                "/internal/talentos/jobs",
                timeout=15.0,
                json={
                    "title": title,
                    "description": description,
                    "required_skills": required_skills,
                    "location": location,
                    "department": department,
                    "employment_type": employment_type,
                    "external_job_id": external_job_id,
                },
                context={"external_job_id": external_job_id},
            )
        except AiRecruitmentError:
            return None

    async def create_candidate(
        self,
        job_id: str,
        name: str,
        email: str,
        phone: str | None = None,
        resume_url: str | None = None,
    ) -> dict | None:
        try:
            return await self._request(
                "POST",
                f"/internal/talentos/jobs/{job_id}/candidates",
                timeout=15.0,
                json={"name": name, "email": email, "phone": phone, "resume_url": resume_url},
                context={"job_id": job_id, "email": email},
            )
        except AiRecruitmentError:
            return None

    async def trigger_screening(self, job_id: str, candidate_id: str) -> dict | None:
        try:
            return await self._request(
                "POST",
                f"/internal/talentos/jobs/{job_id}/candidates/{candidate_id}/call-now",
                timeout=15.0,
                context={"job_id": job_id, "candidate_id": candidate_id},
            )
        except AiRecruitmentConflict:
            raise
        except AiRecruitmentError:
            return None

    async def get_screening_result(self, job_id: str, candidate_id: str) -> dict | None:
        try:
            return await self._request(
                "GET",
                f"/internal/talentos/jobs/{job_id}/candidates/{candidate_id}/screening",
                timeout=10.0,
                context={"job_id": job_id, "candidate_id": candidate_id},
            )
        except AiRecruitmentNotFound:
            return None
        except AiRecruitmentError:
            return None

    async def get_screening_status(self, job_id: str, candidate_id: str) -> dict | None:
        """Server-computed screening disposition (pending/completed/flagged).

        Unlike get_screening_result, this returns a classification even when no
        screening call exists yet (a candidate with no valid phone is flagged).
        """
        try:
            return await self._request(
                "GET",
                f"/internal/talentos/jobs/{job_id}/candidates/{candidate_id}/screening-status",
                timeout=10.0,
                context={"job_id": job_id, "candidate_id": candidate_id},
            )
        except AiRecruitmentNotFound:
            return None
        except AiRecruitmentError:
            return None

    async def list_interviews(self, job_id: str, candidate_id: str) -> list | None:
        try:
            return await self._request(
                "GET",
                f"/internal/talentos/jobs/{job_id}/candidates/{candidate_id}/interviews",
                timeout=10.0,
                context={"job_id": job_id, "candidate_id": candidate_id},
            )
        except AiRecruitmentError:
            return None

    async def get_settings(self) -> dict | None:
        """Read the POC tenant's system settings (phone geography, retries)."""
        try:
            return await self._request(
                "GET",
                "/api/settings",
                timeout=10.0,
                context={"path": "settings"},
            )
        except AiRecruitmentError:
            return None

    async def update_settings(self, payload: dict) -> dict | None:
        """Best-effort sync of tenant system settings to the POC."""
        try:
            return await self._request(
                "PATCH",
                "/api/settings",
                timeout=10.0,
                json=payload,
                context={"path": "settings"},
            )
        except AiRecruitmentError:
            return None

    async def get_interview_detail(
        self, job_id: str, candidate_id: str, interview_id: str
    ) -> dict | None:
        try:
            return await self._request(
                "GET",
                f"/internal/talentos/jobs/{job_id}/candidates/{candidate_id}/interviews/{interview_id}",
                timeout=10.0,
                context={"job_id": job_id, "candidate_id": candidate_id, "interview_id": interview_id},
            )
        except AiRecruitmentError:
            return None

    async def get_interview_recording_url(
        self, job_id: str, candidate_id: str, interview_id: str
    ) -> str | None:
        try:
            data = await self._request(
                "GET",
                f"/internal/talentos/jobs/{job_id}/candidates/{candidate_id}/interviews/{interview_id}/recording-url",
                timeout=10.0,
                context={"job_id": job_id, "candidate_id": candidate_id, "interview_id": interview_id},
            )
        except AiRecruitmentError:
            return None
        return (data or {}).get("recording_url")

    async def create_candidate_with_screening(
        self,
        external_job_id: str,
        name: str,
        email: str,
        phone: str | None = None,
        external_candidate_id: str | None = None,
        force: bool = False,
    ) -> dict | None:
        DUMMY_UUID = "00000000-0000-0000-0000-000000000000"
        try:
            return await self._request(
                "POST",
                f"/internal/talentos/jobs/{DUMMY_UUID}/candidates/with-screening",
                timeout=30.0,
                json={
                    "name": name,
                    "email": email,
                    "phone": phone,
                    "external_job_id": external_job_id,
                    "external_candidate_id": external_candidate_id,
                    "force": force,
                },
                context={"external_job_id": external_job_id, "external_candidate_id": external_candidate_id},
            )
        except AiRecruitmentError:
            return None

    async def create_candidate_with_interview(
        self,
        external_job_id: str,
        name: str,
        email: str,
        phone: str | None = None,
        external_candidate_id: str | None = None,
        force: bool = False,
        interview_type: str | None = "AI_INTERVIEW",
    ) -> dict | None:
        DUMMY_UUID = "00000000-0000-0000-0000-000000000000"
        try:
            return await self._request(
                "POST",
                f"/internal/talentos/jobs/{DUMMY_UUID}/candidates/with-interview",
                timeout=30.0,
                json={
                    "name": name,
                    "email": email,
                    "phone": phone,
                    "external_job_id": external_job_id,
                    "external_candidate_id": external_candidate_id,
                    "force": force,
                    "interview_type": interview_type,
                },
                context={"external_job_id": external_job_id, "external_candidate_id": external_candidate_id},
            )
        except AiRecruitmentError:
            return None

    async def list_candidates(self, job_id: str) -> list | None:
        try:
            return await self._request(
                "GET",
                f"/internal/talentos/jobs/{job_id}/candidates",
                timeout=10.0,
                context={"job_id": job_id},
            )
        except AiRecruitmentError:
            return None

    async def get_job_questions(
        self, job_id: str, external_job_id: str | None = None
    ) -> dict | None:
        params = {"external_job_id": external_job_id} if external_job_id else None
        try:
            return await self._request(
                "GET",
                f"/internal/talentos/jobs/{job_id}/questions",
                timeout=10.0,
                params=params,
                context={"job_id": job_id, "external_job_id": external_job_id},
            )
        except AiRecruitmentError:
            return None

    async def get_call_window(
        self, job_id: str, external_job_id: str | None = None
    ) -> dict | None:
        params = {"external_job_id": external_job_id} if external_job_id else None
        try:
            return await self._request(
                "GET",
                f"/internal/talentos/jobs/{job_id}/call-window",
                timeout=10.0,
                params=params,
                context={"job_id": job_id, "external_job_id": external_job_id},
            )
        except AiRecruitmentError:
            return None

    async def update_call_window(
        self,
        job_id: str,
        screening_call_from: str | None = None,
        screening_call_to: str | None = None,
        screening_timezone: str | None = None,
        external_job_id: str | None = None,
    ) -> dict | None:
        payload: dict = {}
        if screening_call_from is not None:
            payload["screening_call_from"] = screening_call_from
        if screening_call_to is not None:
            payload["screening_call_to"] = screening_call_to
        if screening_timezone is not None:
            payload["screening_timezone"] = screening_timezone
        params = {"external_job_id": external_job_id} if external_job_id else None
        try:
            return await self._request(
                "PUT",
                f"/internal/talentos/jobs/{job_id}/call-window",
                timeout=15.0,
                json=payload,
                params=params,
                context={"job_id": job_id, "external_job_id": external_job_id},
            )
        except AiRecruitmentError:
            return None

    async def update_job_questions(
        self,
        job_id: str,
        screening_questions: list | None = None,
        interview_questions: list | None = None,
        external_job_id: str | None = None,
    ) -> dict | None:
        payload: dict = {}
        if screening_questions is not None:
            payload["screening_questions"] = screening_questions
        if interview_questions is not None:
            payload["interview_questions"] = interview_questions
        params = {"external_job_id": external_job_id} if external_job_id else None
        try:
            return await self._request(
                "PUT",
                f"/internal/talentos/jobs/{job_id}/questions",
                timeout=15.0,
                json=payload,
                params=params,
                context={"job_id": job_id, "external_job_id": external_job_id},
            )
        except AiRecruitmentError:
            return None

    async def schedule_interview(
        self,
        job_id: str,
        candidate_id: str,
        scheduled_date: str,
        scheduled_time: str,
        timezone: str,
    ) -> dict | None:
        """Set the scheduled slot (date/time in an IANA timezone) on a candidate's AI interview."""
        try:
            return await self._request(
                "PUT",
                f"/internal/talentos/jobs/{job_id}/candidates/{candidate_id}/interview/schedule",
                timeout=15.0,
                json={
                    "scheduled_date": scheduled_date,
                    "scheduled_time": scheduled_time,
                    "timezone": timezone,
                },
                context={"job_id": job_id, "candidate_id": candidate_id},
            )
        except AiRecruitmentError:
            return None

    async def clear_interview_schedule(
        self,
        job_id: str,
        candidate_id: str,
    ) -> dict | None:
        """Clear the scheduled slot so the candidate can join immediately."""
        try:
            return await self._request(
                "PUT",
                f"/internal/talentos/jobs/{job_id}/candidates/{candidate_id}/interview/schedule",
                timeout=15.0,
                json=None,
                context={"job_id": job_id, "candidate_id": candidate_id},
            )
        except AiRecruitmentError:
            return None

from collections.abc import AsyncGenerator

import httpx

from app.common.clients.base_client import BaseClient, ClientError
from app.core.config import settings
from app.core.logger import get_logger
from app.common.schemas.evaluation import AIEvaluationRequest, AIEvaluationResponse
from app.common.schemas.generate import AIGenerateRequest, AIGenerateResponse
from app.common.schemas.review_questions import (
    GenerateReviewQuestionsRequest,
    GenerateReviewQuestionsResponse,
)

logger = get_logger(__name__)


class AIClientError(ClientError):
    """Raised when the AI service returns an error or is unreachable."""


class AIClient(BaseClient):
    """Client for the internal talentOS_AI microservice.

    Endpoints
    ---------
    - ``POST /api/v1/evaluation/evaluate-resume`` — resume scoring
    - ``POST /api/v1/evaluation/generate-review-questions`` — post-interview rating questions
    - ``POST /api/v1/generate`` — generic prompt + input data + JSON Schema structured output
    - ``POST /api/v1/chat/stream`` — streaming chat (async)
    """

    def __init__(self) -> None:
        super().__init__(
            base_url=settings.AI_SERVICE_BASE_URL,
            timeout=settings.AI_SERVICE_TIMEOUT,
            max_retries=2,
        )
        self._stream_client: httpx.AsyncClient | None = None

    @property
    def _service_name(self) -> str:
        return "AI Service"

    # ── resume evaluation (sync) ─────────────────────────────────

    def evaluate_resume(self, resume_txt: str, jd_details: str, custom_evaluation_criteria: str = "") -> AIEvaluationResponse:
        request = AIEvaluationRequest(
            resume_txt=resume_txt,
            custom_evaluation_criteria=custom_evaluation_criteria,
            jd_details=jd_details,
        )
        response = self._post("api/v1/evaluation/evaluate-resume", json_data=request.model_dump())
        return AIEvaluationResponse.model_validate(response.json())

    # ── review questions (sync) ──────────────────────────────────

    def generate_review_questions(
        self,
        transcription: str | None = None,
        jd_details: str | None = None,
    ) -> GenerateReviewQuestionsResponse:
        request = GenerateReviewQuestionsRequest(
            transcription=transcription,
            jd_details=jd_details,
        )
        response = self._post(
            "api/v1/evaluation/generate-review-questions",
            json_data=request.model_dump(exclude_none=True),
        )
        return GenerateReviewQuestionsResponse.model_validate(response.json())

    # ── generic structured generation (sync) ────────────────────

    def generate(
        self,
        prompt: str,
        input_data: dict,
        response_schema: dict,
        use_evaluation_model: bool = False,
    ) -> AIGenerateResponse:
        """Run a prompt with input data and get JSON matching the caller's JSON Schema."""
        request = AIGenerateRequest(
            prompt=prompt,
            input_data=input_data,
            response_schema=response_schema,
            use_evaluation_model=use_evaluation_model,
        )
        response = self._post("api/v1/generate", json_data=request.model_dump())
        return AIGenerateResponse.model_validate(response.json())

    # ── streaming chat (async) ───────────────────────────────────

    async def stream_chat(
        self,
        message: str,
        thread_id: str,
        authorization: str | None = None,
    ) -> AsyncGenerator[bytes, None]:
        """Stream chat response from the AI service.

        ``authorization`` is the validated caller's ``Authorization`` header
        (e.g. ``"Bearer <jwt>"``) and is forwarded wholesale so the AI/MCP
        layer can impersonate the end user on subsequent backend calls.

        Yields raw NDJSON bytes that the caller should parse.
        """
        url = f"{self._base_url}/api/v1/chat/stream"
        headers: dict[str, str] = {}
        if authorization:
            headers["Authorization"] = authorization
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            async with client.stream(
                "POST",
                url,
                json={"message": message, "thread_id": thread_id},
                headers=headers,
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    yield chunk

    # ── error mapping ────────────────────────────────────────────

    def _map_error(self, exc: Exception) -> Exception:
        from httpx import HTTPStatusError

        if isinstance(exc, HTTPStatusError):
            status = exc.response.status_code
            body = _try_extract_body(exc.response)
            return AIClientError(
                message=f"AI service returned {status}: {body}",
                code=self._ERROR_CODES,
                status_code=status,
            )
        return AIClientError(
            message=f"AI service unreachable: {exc}",
            code=self._ERROR_CODES,
            status_code=502,
        )

    @property
    def _ERROR_CODES(self):  # noqa: N802
        from app.core.constants import ErrorCode
        return ErrorCode.INTERNAL_ERROR


def _try_extract_body(response: httpx.Response) -> str:
    try:
        data = response.json()
    except Exception:
        return response.text[:200]
    if isinstance(data, dict):
        detail = data.get("detail")
        if isinstance(detail, str) and detail:
            return detail
        return data.get("error", data.get("message", str(data)))
    return str(data)

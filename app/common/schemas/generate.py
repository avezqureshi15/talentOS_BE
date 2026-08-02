from typing import Any

from pydantic import BaseModel


class AIGenerateRequest(BaseModel):
    """Request body for talentOS_AI POST /api/v1/generate."""

    prompt: str
    input_data: dict[str, Any] = {}
    response_schema: dict[str, Any]
    use_evaluation_model: bool = False


class AIGenerateResponse(BaseModel):
    """Response body from the AI generate endpoint."""

    result: dict[str, Any]

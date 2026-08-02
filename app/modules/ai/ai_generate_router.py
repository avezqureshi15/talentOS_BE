from fastapi import APIRouter, Depends

from app.common.clients.ai_client import AIClient
from app.common.schemas.generate import AIGenerateRequest, AIGenerateResponse
from app.core.config import settings
from app.modules.auth.auth_dependencies import get_current_user
from app.modules.auth.auth_schema import UserInfo

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/ai", tags=["ai"])


@router.post("/generate", response_model=AIGenerateResponse)
def generate_structured(
    payload: AIGenerateRequest,
    current_user: UserInfo = Depends(get_current_user),
) -> AIGenerateResponse:
    """Generate structured output from a prompt, input data, and a caller-provided JSON Schema."""
    return AIClient().generate(
        prompt=payload.prompt,
        input_data=payload.input_data,
        response_schema=payload.response_schema,
        use_evaluation_model=payload.use_evaluation_model,
    )

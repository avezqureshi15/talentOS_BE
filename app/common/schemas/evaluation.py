from pydantic import BaseModel


class AIEvaluationRequest(BaseModel):
    """Request body for talentOS_AI POST /api/v1/evaluation/evaluate-resume."""

    resume_txt: str
    custom_evaluation_criteria: str
    jd_details: str


class AIEvaluationResponse(BaseModel):
    """Response body from the AI evaluation endpoint."""

    resume_summary: str
    overall_score_percentage: int
    rejection_details: list[dict] = []

from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.schemas.application import ApplicationSubmitIn, ApplicationSubmitOut
from app.services.application_service import ApplicationService

router = APIRouter(prefix="/apply", tags=["applications"])


@router.post("", response_model=ApplicationSubmitOut)
async def submit_application(
    body: ApplicationSubmitIn,
    background_tasks: BackgroundTasks,
):
    """
    Public endpoint — no auth required.
    Called directly from the Webknot careers page when a candidate applies.
    Returns immediately, evaluation runs in background via Celery.
    """
    candidate_id = await ApplicationService.receive(body, background_tasks)
    return ApplicationSubmitOut(candidate_id=candidate_id)

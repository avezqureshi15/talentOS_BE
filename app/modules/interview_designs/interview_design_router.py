from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.authorization import require_permission
from app.core.permissions import Permission
from app.db.session import get_db
from app.modules.interview_designs.interview_design_schema import (
    InterviewDesignResponse,
    InterviewDesignUpdate,
)
from app.modules.interview_designs.interview_design_service import (
    get_or_seed_design,
    update_design,
)

router = APIRouter(
    prefix="/api/v1/hiring-requests/{hiring_request_id}/ai",
    tags=["interview-design"],
    dependencies=[Depends(require_permission(Permission.APPLICATION_VIEW))],
)


@router.get("/questions", response_model=InterviewDesignResponse)
async def get_questions(
    hiring_request_id: str,
    db: Session = Depends(get_db),
):
    return await get_or_seed_design(hiring_request_id, db)


@router.put(
    "/questions",
    response_model=InterviewDesignResponse,
    dependencies=[Depends(require_permission(Permission.INTERVIEW_PLAN_EDIT))],
)
async def update_questions(
    hiring_request_id: str,
    body: InterviewDesignUpdate,
    db: Session = Depends(get_db),
):
    return await update_design(hiring_request_id, body, db)

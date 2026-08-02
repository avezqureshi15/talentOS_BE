from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.authorization import require_permission
from app.core.permissions import Permission
from app.db.session import get_db
from app.modules.call_windows.call_window_schema import (
    CallWindowResponse,
    CallWindowUpdate,
)
from app.modules.call_windows.call_window_service import (
    get_call_window,
    update_call_window,
)

router = APIRouter(
    prefix="/api/v1/hiring-requests/{hiring_request_id}/call-window",
    tags=["call-window"],
    dependencies=[Depends(require_permission(Permission.APPLICATION_VIEW))],
)


@router.get("", response_model=CallWindowResponse)
async def get_window(
    hiring_request_id: str,
    db: Session = Depends(get_db),
):
    return await get_call_window(hiring_request_id, db)


@router.put(
    "",
    response_model=CallWindowResponse,
    dependencies=[Depends(require_permission(Permission.INTERVIEW_PLAN_EDIT))],
)
async def update_window(
    hiring_request_id: str,
    body: CallWindowUpdate,
    db: Session = Depends(get_db),
):
    """Update the screening call window on the linked ai-recruitment-poc job."""
    return await update_call_window(hiring_request_id, body, db)

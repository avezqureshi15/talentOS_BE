from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.authorization import require_permission
from app.core.config import settings
from app.core.permissions import Permission
from app.db.session import get_db
from app.modules.auth.auth_dependencies import get_current_user
from app.modules.auth.auth_schema import UserInfo
from app.modules.forms.form_service import FormService
from app.modules.slots.slot_schema import (
    BatchEmployeeSlotsResponse,
    SlotDetailResponse,
    SlotListItemResponse,
    SlotResponse,
    SlotStatusUpdate,
    SlotSummaryResponse,
    SlotsCreateRequest,
    SlotsCreateResponse,
)
from app.modules.slots.slot_service import SlotService

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/slots", tags=["slots"])


def _tenant_id_for_user(current_user: UserInfo) -> int | None:
    return None if current_user.role == "superadmin" else current_user.tenant_id


@router.get(
    "/summary",
    response_model=SlotSummaryResponse,
    dependencies=[Depends(require_permission(Permission.SLOT_VIEW_ALL))],
)
def get_slots_summary(
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    return SlotService(db).get_summary(_tenant_id_for_user(current_user))


@router.get(
    "/by-employee/{employee_id}",
    response_model=list[SlotListItemResponse] | list[SlotDetailResponse],
    dependencies=[Depends(require_permission(Permission.SLOT_VIEW_ALL))],
)
def get_slots_for_employee(
    employee_id: int,
    detail: bool = Query(False, description="Return full slot fields for management UI"),
    db: Session = Depends(get_db),
):
    return SlotService(db).get_slots_for_employee(employee_id, detail=detail)


@router.patch(
    "/{slot_id}",
    response_model=SlotResponse,
    dependencies=[Depends(require_permission(Permission.SLOT_VIEW_ALL))],
)
def update_slot_status(
    slot_id: UUID,
    data: SlotStatusUpdate,
    db: Session = Depends(get_db),
):
    return SlotService(db).update_slot_status(slot_id, data)


@router.post("/", response_model=SlotsCreateResponse, status_code=status.HTTP_201_CREATED)
def create_slots(data: SlotsCreateRequest, db: Session = Depends(get_db)):
    service = SlotService(db)
    result = service.create_slots(data)
    FormService(db).mark_slots_form_submitted(data.emp_id)
    return result


@router.get(
    "/employee",
    response_model=BatchEmployeeSlotsResponse,
    dependencies=[Depends(require_permission(Permission.SLOT_VIEW_ALL))],
)
def get_slots_for_employees(
    emp_ids: list[str] = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    return SlotService(db).get_slots_for_employees(emp_ids)

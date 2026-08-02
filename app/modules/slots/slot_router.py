from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.core.authorization import require_permission
from app.core.permissions import Permission
from app.modules.forms.form_service import FormService
from app.modules.slots.slot_schema import (
    BatchEmployeeSlotsResponse,
    SlotListItemResponse,
    SlotsCreateRequest,
    SlotsCreateResponse,
)
from app.modules.slots.slot_service import SlotService

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/slots", tags=["slots"])


@router.get("/by-employee/{employee_id}", response_model=list[SlotListItemResponse], dependencies=[Depends(require_permission(Permission.SLOT_VIEW_ALL))])
def get_slots_for_employee(
    employee_id: int,
    db: Session = Depends(get_db),
):
    service = SlotService(db)
    return service.get_slots_for_employee(employee_id)


@router.post("/", response_model=SlotsCreateResponse, status_code=status.HTTP_201_CREATED)
def create_slots(data: SlotsCreateRequest, db: Session = Depends(get_db)):
    service = SlotService(db)
    result = service.create_slots(data)
    FormService(db).mark_slots_form_submitted(data.emp_id)
    return result


@router.get("/employee", response_model=BatchEmployeeSlotsResponse, dependencies=[Depends(require_permission(Permission.SLOT_VIEW_ALL))])
def get_slots_for_employees(
    emp_ids: list[str] = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    service = SlotService(db)
    return service.get_slots_for_employees(emp_ids)

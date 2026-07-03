from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.modules.slots.slot_schema import (
    EmployeeSlotsResponse,
    SlotResponse,
    SlotStatusUpdate,
    SlotsCreateRequest,
    SlotsCreateResponse,
)
from app.modules.slots.slot_service import SlotService

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/slots", tags=["slots"])


@router.post("/", response_model=SlotsCreateResponse, status_code=status.HTTP_201_CREATED)
def create_slots(data: SlotsCreateRequest, db: Session = Depends(get_db)):
    service = SlotService(db)
    return service.create_slots(data)


@router.get("/employee/{emp_id}", response_model=EmployeeSlotsResponse)
def get_slots_for_employee(
    emp_id: str,
    status: str | None = Query(
        default=None,
        description="Filter by status: available (default), booked, inactive. Use empty string for all.",
    ),
    db: Session = Depends(get_db),
):
    service = SlotService(db)
    return service.get_slots_for_employee(emp_id, status)


@router.patch("/{slot_id}/status", response_model=SlotResponse)
def update_slot_status(slot_id: UUID, data: SlotStatusUpdate, db: Session = Depends(get_db)):
    service = SlotService(db)
    return service.update_slot_status(slot_id, data.status)


@router.delete("/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_slot(slot_id: UUID, db: Session = Depends(get_db)):
    service = SlotService(db)
    service.delete_slot(slot_id)

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.modules.slots.slot_schema import (
    BatchEmployeeSlotsResponse,
    SlotsCreateRequest,
    SlotsCreateResponse,
)
from app.modules.slots.slot_service import SlotService

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/slots", tags=["slots"])


@router.post("/", response_model=SlotsCreateResponse, status_code=status.HTTP_201_CREATED)
def create_slots(data: SlotsCreateRequest, db: Session = Depends(get_db)):
    service = SlotService(db)
    return service.create_slots(data)


@router.get("/employee", response_model=BatchEmployeeSlotsResponse)
def get_slots_for_employees(
    emp_ids: list[str] = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    service = SlotService(db)
    return service.get_slots_for_employees(emp_ids)

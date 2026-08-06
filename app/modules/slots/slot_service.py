from sqlalchemy import exc as sa_exc
from sqlalchemy.orm import Session

from app.common.exceptions.slot_exception import (
    EmployeeNotFoundException,
)
from app.core.logger import get_logger
from app.modules.employees.employee_directory_repository import EmployeeDirectoryRepository
from app.modules.slots.slot_actions import resolve_slot_action
from app.modules.slots.slot_model import Slot, SlotStatus
from app.modules.slots.slot_presenter import now_ist, present_slot_item, to_ist
from app.modules.slots.slot_repository import SlotRepository
from app.modules.slots.slot_schema import (
    BatchEmployeeSlotsResponse,
    EmployeeSlotsResponse,
    SkippedSlot,
    SlotListItemResponse,
    SlotResponse,
    SlotsCreateRequest,
    SlotsCreateResponse,
)

logger = get_logger(__name__)


class SlotService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = SlotRepository(db)
        self.employees = EmployeeDirectoryRepository(db)

    def create_slots(self, data: SlotsCreateRequest) -> SlotsCreateResponse:
        employee = self.employees.get_by_emp_id(data.emp_id)
        if not employee:
            raise EmployeeNotFoundException(data.emp_id)

        logger.info("Creating %d slot(s) for emp_id=%s", len(data.slots), data.emp_id)

        working_slots: list[Slot] = self.repository.get_slots_for_employee(
            employee.id,
            status=None,
            include_past=True,
        )

        result: list[SlotResponse] = []
        skipped: list[SkippedSlot] = []

        try:
            current_ist = now_ist()
            for slot_data in data.slots:
                if to_ist(slot_data.start_at) <= current_ist:
                    skipped.append(
                        SkippedSlot(
                            start_at=slot_data.start_at,
                            end_at=slot_data.end_at,
                            reason="not_in_future",
                        )
                    )
                    continue

                action = resolve_slot_action(slot_data, working_slots)

                if action.kind == "skip":
                    assert action.reason is not None
                    skipped.append(
                        SkippedSlot(
                            start_at=slot_data.start_at,
                            end_at=slot_data.end_at,
                            reason=action.reason,
                        )
                    )
                    continue

                if action.kind == "update":
                    assert action.target is not None
                    updated = self.repository.update_slot_times(
                        action.target,
                        start_at=action.start_at,
                        end_at=action.end_at,
                        status=action.status,
                    )
                    result.append(SlotResponse.model_validate(updated))
                    continue

                slot = self.repository.create_slot(
                    employee_id=employee.id,
                    start_at=slot_data.start_at,
                    end_at=slot_data.end_at,
                )
                working_slots.append(slot)
                result.append(SlotResponse.model_validate(slot))

            self.db.commit()
        except sa_exc.SQLAlchemyError as exc:
            self.db.rollback()
            logger.error("Failed to create slots for emp_id=%s: %s", data.emp_id, str(exc))
            raise

        logger.info(
            "Processed %d slot(s) for emp_id=%s: %d in data, %d skipped",
            len(data.slots),
            data.emp_id,
            len(result),
            len(skipped),
        )
        return SlotsCreateResponse(data=result, skipped=skipped)

    def get_slots_for_employee(self, employee_id: int) -> list[SlotListItemResponse]:
        slots = self.repository.get_slots_for_employee(
            employee_id,
            status=SlotStatus.AVAILABLE.value,
            include_past=False,
        )
        return [present_slot_item(s) for s in slots]

    def get_slots_for_employees(self, emp_ids: list[str]) -> BatchEmployeeSlotsResponse:
        data: list[EmployeeSlotsResponse] = []
        for emp_id in emp_ids:
            employee = self.employees.get_by_emp_id(emp_id)
            if not employee:
                data.append(EmployeeSlotsResponse(emp_id=emp_id, slots=[]))
                continue
            slots = self.repository.get_slots_for_employee(
                employee.id,
                status=SlotStatus.AVAILABLE.value,
                include_past=False,
            )
            data.append(
                EmployeeSlotsResponse(
                    emp_id=emp_id,
                    slots=[
                        present_slot_item(s)
                        for s in slots
                    ],
                )
            )
        return BatchEmployeeSlotsResponse(data=data)

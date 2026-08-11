import asyncio
from datetime import datetime
from uuid import UUID

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import exc as sa_exc
from sqlalchemy.orm import Session

from app.common.exceptions.hiring_request_exception import (
    HiringRequestNotCreatedException,
    HiringRequestNotDeletedException,
    HiringRequestNotFoundException,
    HiringRequestNotUpdatedException,
)
from app.core.job_access import can_create_job
from app.core.logger import get_logger
from app.db.session import SessionLocal
from app.modules.auth.auth_schema import UserInfo
from app.modules.hiring_requests.hiring_request_model import HiringRequest
from app.modules.hiring_requests.hiring_request_repository import HiringRequestRepository
from app.modules.hiring_requests.hiring_request_schema import (
    HiringRequestCreate,
    HiringRequestResponse,
    HiringRequestUpdate,
)
from app.modules.hiring_requests.location_utils import format_locations
from app.modules.jobs.job_schema import JobCreate, JobUpdate
from app.modules.jobs.job_service import JobService
from app.modules.job_teams.job_team_repository import JobTeamRepository

logger = get_logger(__name__)


def _sync_rh_job(hr_id: str) -> None:
    from app.core.ai_recruitment_client import AiRecruitmentClient

    db = SessionLocal()
    try:
        hr = db.query(HiringRequest).filter(HiringRequest.id == hr_id).first()
        if not hr or hr.rh_external_job_id:
            return

        client = AiRecruitmentClient()
        created = asyncio.run(
            client.create_job(
                title=hr.title,
                description=hr.description,
                required_skills=hr.requirements,
                location=format_locations(hr.location),
                department=hr.department,
                employment_type=hr.type,
                external_job_id=str(hr.id),
            )
        )
        if not created or not created.get("id"):
            logger.warning("RH job sync failed for hiring request %s", hr_id)
            return

        hr.rh_external_job_id = created["id"]
        db.commit()
        logger.info("RH job created for hiring request %s: rh_job_id=%s", hr_id, created["id"])
    except Exception:
        logger.exception("RH job sync failed for hiring request %s", hr_id)
    finally:
        db.close()


class HiringRequestService:
    def __init__(self, db: Session):
        self.repository = HiringRequestRepository(db)
        self.job_service = JobService()

    def _next_serial(self) -> int:
        total = self.repository.count_active()
        return total + 1

    def _resolve_creator_employee_id(self, user_id: int) -> int | None:
        """Resolve a user id to a real ``employees.id`` for job-team rows
        (``job_team_members.employee_id`` is an employees FK). Falls back to
        creating/linking the employee row so new creators always get a valid
        owner entry."""
        from app.modules.employees.employee_lookup import ensure_employee_for_user
        from app.modules.users.user_model import User

        user = self.repository.db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        employee = ensure_employee_for_user(self.repository.db, user)
        return employee.id if employee else None

    def _notify_job_created(self, hr, tenant_id: int, current_user: UserInfo) -> None:
        from app.modules.notifications.notification_model import NotificationType
        from app.modules.notifications.notification_service import NotificationService

        NotificationService(self.repository.db).notify_tenant_admins(
            tenant_id,
            notification_type=NotificationType.JOB_CREATED.value,
            title="New job created",
            body=f"{current_user.name} created \"{hr.title}\".",
            action_url=f"/hiring-requests/{hr.id}",
            action_label="View job",
            job_id=hr.id,
        )
        self.repository.db.commit()

    def create_hiring_request(
        self,
        data: HiringRequestCreate,
        background_tasks: BackgroundTasks | None = None,
        current_user: UserInfo | None = None,
    ) -> dict:
        tenant_id = data.tenant_id
        if current_user is not None:
            if current_user.role == "superadmin":
                if tenant_id is None:
                    raise HTTPException(status_code=400, detail="tenant_id is required when creating as superadmin")
            else:
                tenant_id = current_user.tenant_id
                if tenant_id is None:
                    raise HTTPException(status_code=400, detail="tenant_id is required to create a hiring request")

        serial = self._next_serial()
        prefixed = f"#{serial} {data.title}"
        logger.info("Creating hiring request: title=%s tenant_id=%s", prefixed, tenant_id)
        data.title = prefixed
        job_dump = data.model_dump(exclude={"custom_evaluation_criteria", "tenant_id"})
        job_dump["location"] = format_locations(job_dump.get("location"))
        job_payload = JobCreate(**job_dump)
        job_response = self.job_service.create_job(job_payload)
        external_job_id = job_response.get("data", {}).get("id")

        try:
            payload = data.model_dump()
            payload["external_job_id"] = external_job_id
            payload["tenant_id"] = tenant_id
            local_record = self.repository.create(payload)
        except sa_exc.SQLAlchemyError as exc:
            logger.exception(
                "Hiring request created in Supabase but DB write failed: title=%s",
                data.title,
            )
            raise HiringRequestNotCreatedException(
                "Job listing created in Supabase but failed to save locally"
            ) from exc

        if current_user is not None:
            owner_row = self._resolve_creator_employee_id(current_user.id)
            if owner_row is None:
                logger.warning(
                    "No linked employee for creator user_id=%d — job owner not added to team",
                    current_user.id,
                )
            else:
                JobTeamRepository(self.repository.db).add_member(
                    local_record.id,
                    owner_row,
                    is_owner=True,
                )
                logger.info(
                    "Creator added as owner: job_id=%s user_id=%d employee_id=%d",
                    local_record.id,
                    current_user.id,
                    owner_row,
                )
                self._notify_job_created(local_record, tenant_id, current_user)

        if background_tasks is not None:
            background_tasks.add_task(_sync_rh_job, str(local_record.id))

        response = HiringRequestResponse.model_validate(local_record).model_dump()
        return {"data": response, "supabase_job": job_response}

    def get_hiring_request_by_id(self, hiring_request_id: UUID) -> dict:
        logger.info("Fetching hiring request: id=%s", hiring_request_id)
        record = self.repository.resolve_to_external_job_id(hiring_request_id)
        if not record:
            raise HiringRequestNotFoundException(str(hiring_request_id))
        response = HiringRequestResponse.model_validate(record).model_dump()
        return {"data": response}

    def get_all_hiring_requests(
        self,
        search: str | None = None,
        department: str | None = None,
        location: str | None = None,
        type: str | None = None,
        is_active: bool | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        page: int = 1,
        per_page: int = 10,
        tenant_id: int | None = None,
        current_user: UserInfo | None = None,
    ) -> dict:
        logger.info("Fetching hiring requests from local DB search=%s", search)
        records, total = self.repository.get_all(
            search=search,
            department=department,
            location=location,
            type=type,
            is_active=is_active,
            created_from=created_from,
            created_to=created_to,
            page=page,
            per_page=per_page,
            tenant_id=tenant_id,
            user=current_user,
        )
        items = [HiringRequestResponse.model_validate(r).model_dump() for r in records]
        total_pages = max(1, (total + per_page - 1) // per_page)
        return {
            "data": items,
            "count": len(items),
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "total": total,
            "has_more": page < total_pages,
            "can_create": can_create_job(self.repository.db, current_user) if current_user is not None else False,
        }

    def update_hiring_request(self, hiring_request_id: UUID, data: HiringRequestUpdate) -> dict:
        logger.info("Updating hiring request: id=%s", hiring_request_id)
        record = self.repository.resolve_to_external_job_id(hiring_request_id)
        if not record:
            raise HiringRequestNotFoundException(str(hiring_request_id))

        if record.external_job_id:
            job_dump = data.model_dump(exclude={"custom_evaluation_criteria"}, exclude_unset=True)
            if "location" in job_dump:
                job_dump["location"] = format_locations(job_dump.get("location"))
            job_payload = JobUpdate(**job_dump)
            self.job_service.update_job(record.external_job_id, job_payload)

        try:
            updated = self.repository.update(record, data.model_dump(exclude_unset=True))
        except sa_exc.SQLAlchemyError as exc:
            logger.exception("Hiring request DB update failed: id=%s", hiring_request_id)
            raise HiringRequestNotUpdatedException("Failed to save updated hiring request locally") from exc

        response = HiringRequestResponse.model_validate(updated).model_dump()
        return {"data": response}

    def toggle_hiring_request_status(self, hiring_request_id: UUID) -> dict:
        logger.info("Toggling hiring request status: id=%s", hiring_request_id)
        record = self.repository.resolve_to_external_job_id(hiring_request_id)
        if not record:
            raise HiringRequestNotFoundException(str(hiring_request_id))

        new_status = not record.is_active

        if record.external_job_id:
            job_payload = JobUpdate(is_active=new_status)
            self.job_service.update_job(record.external_job_id, job_payload)

        try:
            updated = self.repository.update(record, {"is_active": new_status})
        except sa_exc.SQLAlchemyError as exc:
            logger.exception("Hiring request DB update failed: id=%s", hiring_request_id)
            raise HiringRequestNotUpdatedException("Failed to update hiring request status locally") from exc

        response = HiringRequestResponse.model_validate(updated).model_dump()
        return {"data": response}

    def get_types(self, current_user: UserInfo | None = None) -> dict:
        types = self.repository.get_distinct_types(user=current_user)
        return {"data": types}

    def get_locations(self, current_user: UserInfo | None = None) -> dict:
        locations = self.repository.get_distinct_locations(user=current_user)
        return {"data": locations}

    def get_departments(self, current_user: UserInfo | None = None) -> dict:
        departments = self.repository.get_distinct_departments(user=current_user)
        return {"data": departments}

    def delete_hiring_request(self, hiring_request_id: UUID) -> dict:
        logger.info("Deleting hiring request: id=%s", hiring_request_id)
        record = self.repository.resolve_to_external_job_id(hiring_request_id)
        if not record:
            raise HiringRequestNotFoundException(str(hiring_request_id))

        if record.external_job_id:
            self.job_service.delete_job(record.external_job_id)

        try:
            self.repository.soft_delete(record)
        except sa_exc.SQLAlchemyError as exc:
            logger.exception("Hiring request DB soft delete failed: id=%s", hiring_request_id)
            raise HiringRequestNotDeletedException("Failed to soft delete hiring request locally") from exc

        logger.info("Hiring request soft deleted: id=%s", hiring_request_id)
        return {"message": "Hiring request deleted successfully"}

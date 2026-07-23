from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.core.constants import DEFAULT_PAGE_SIZE
from app.modules.users.user_repository import UserRepository
from app.modules.users.user_schema import PaginatedUserResponse, UserResponse

logger = get_logger(__name__)


class UserService:
    def __init__(self, db: Session):
        self.repository = UserRepository(db)

    def get_benched_candidates(self, designation: str) -> dict:
        logger.info("Fetching benched candidates: designation=%s", designation)
        users = self.repository.get_benched_by_designation(designation)
        data = [UserResponse.model_validate(u) for u in users]
        logger.debug("Found %d benched candidates for designation=%s", len(data), designation)
        return {"data": data, "count": len(data)}

    def get_user_by_emp_id(self, emp_id: str) -> UserResponse | None:
        logger.info("Fetching user by emp_id: %s", emp_id)
        user = self.repository.get_by_emp_id(emp_id)
        if not user:
            logger.warning("User not found: emp_id=%s", emp_id)
            return None
        return UserResponse.model_validate(user)

    def search_users(
        self,
        query: str | None = None,
        page: int = 1,
        per_page: int = DEFAULT_PAGE_SIZE,
        slots_info: bool = False,
        tenant_id: int | None = None,
    ) -> PaginatedUserResponse:
        logger.info("Searching users: query=%s page=%d per_page=%d slots_info=%s tenant_id=%s", query, page, per_page, slots_info, tenant_id)
        result, total = self.repository.search_paginated(query, page, per_page, slots_info, tenant_id=tenant_id)

        if slots_info:
            data = []
            for u, count in result:
                user_data = UserResponse.model_validate(u)
                user_data.slots_count = count
                user_data.has_slots = count > 0
                data.append(user_data)
        else:
            data = [UserResponse.model_validate(u) for u in result]

        has_more = (page * per_page) < total
        logger.debug("Found %d users (total=%d, has_more=%s)", len(data), total, has_more)
        return PaginatedUserResponse(data=data, total=total, page=page, per_page=per_page, has_more=has_more)

    def list_users(self, page: int = 1, per_page: int = 20, q: str | None = None) -> PaginatedUserResponse:
        logger.info("Listing users: page=%d per_page=%d q=%s", page, per_page, q)
        users, total = self.repository.list_all(page, per_page, q)
        data = [UserResponse.model_validate(u) for u in users]
        has_more = (page * per_page) < total
        return PaginatedUserResponse(data=data, total=total, page=page, per_page=per_page, has_more=has_more)

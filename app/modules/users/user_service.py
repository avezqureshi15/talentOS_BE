from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.modules.users.user_repository import UserRepository
from app.modules.users.user_schema import UserResponse

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

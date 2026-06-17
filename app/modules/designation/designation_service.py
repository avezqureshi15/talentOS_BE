from sqlalchemy.orm import Session

from app.common.exceptions.designation_exception import DesignationNotFoundException
from app.core.logger import get_logger
from app.modules.designation.designation_repository import DesignationRepository

logger = get_logger(__name__)


class DesignationService:
    def __init__(self, db: Session):
        self.repository = DesignationRepository(db)

    def get_all_designations(self) -> list[str]:
        logger.info("Fetching all unique designation names")
        names = self.repository.get_all_names()
        logger.debug("Found %d unique designations", len(names))
        return names

    def get_designation_detail(self, name: str) -> dict:
        logger.info("Fetching designation detail: name=%s", name)
        data = self.repository.get_designation_with_details(name)
        if not data:
            logger.error("Designation not found: name=%s", name)
            raise DesignationNotFoundException(name)
        logger.debug("Designation detail found: name=%s | kpis=%d", name, len(data["kpis"]))
        return data

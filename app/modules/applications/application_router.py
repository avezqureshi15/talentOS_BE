from fastapi import APIRouter, status

from app.core.config import settings
from app.modules.applications.application_schema import ApplicationCreate
from app.modules.applications.application_service import ApplicationService

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/applications", tags=["applications"])


@router.get("/")
def get_all_applications():
    service = ApplicationService()
    return service.get_all_applications()


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_application(data: ApplicationCreate):
    service = ApplicationService()
    return service.create_application(data)

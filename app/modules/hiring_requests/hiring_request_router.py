from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.modules.hiring_requests.hiring_request_schema import HiringRequestCreate
from app.modules.hiring_requests.hiring_request_service import HiringRequestService

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}/hiring-requests", tags=["hiring-requests"])


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_hiring_request(data: HiringRequestCreate, db: Session = Depends(get_db)):
    service = HiringRequestService(db)
    return service.create_hiring_request(data)


@router.get("/")
def get_all_hiring_requests(db: Session = Depends(get_db)):
    service = HiringRequestService(db)
    return service.get_all_hiring_requests()

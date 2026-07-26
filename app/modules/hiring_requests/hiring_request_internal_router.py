from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.service_auth import verify_service_jwt
from app.modules.hiring_requests.hiring_request_schema import HiringRequestCreate
from app.modules.hiring_requests.hiring_request_service import HiringRequestService

router = APIRouter()


@router.post("/hiring-requests", status_code=201)
def create_hiring_request_internal(
    data: HiringRequestCreate,
    db: Session = Depends(get_db),
    _=Depends(verify_service_jwt),
):
    service = HiringRequestService(db)
    result = service.create_hiring_request(data)
    return result

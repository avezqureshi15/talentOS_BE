from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.service_auth import verify_service_api_key, verify_service_jwt
from app.modules.hiring_requests.hiring_request_model import HiringRequest
from app.modules.hiring_requests.hiring_request_schema import HiringRequestCreate, HiringRequestResponse
from app.modules.hiring_requests.hiring_request_service import HiringRequestService

router = APIRouter()


@router.post("/hiring-requests", status_code=201)
def create_hiring_request_internal(
    data: HiringRequestCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _=Depends(verify_service_jwt),
):
    service = HiringRequestService(db)
    result = service.create_hiring_request(data, background_tasks)
    return result


@router.get("/hiring-requests/{hiring_request_id}", response_model=HiringRequestResponse)
def get_hiring_request_internal(
    hiring_request_id: str,
    db: Session = Depends(get_db),
    _=Depends(verify_service_api_key),
):
    hr = db.query(HiringRequest).filter(HiringRequest.id == hiring_request_id).first()
    if not hr:
        raise HTTPException(status_code=404, detail="Hiring request not found")
    return hr

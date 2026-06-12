from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.modules.designation.designation_schema import DesignationDetailResponse
from app.modules.designation.designation_service import DesignationService

router = APIRouter(prefix=f"{settings.API_V1_PREFIX}", tags=["designations"])


@router.get("/designations", response_model=list[str])
def get_all_designations(db: Session = Depends(get_db)):
    service = DesignationService(db)
    return service.get_all_designations()


@router.get("/designation", response_model=DesignationDetailResponse)
def get_designation_detail(name: str = Query(...), db: Session = Depends(get_db)):
    service = DesignationService(db)
    return service.get_designation_detail(name)

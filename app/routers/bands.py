from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import AllowedUser
from app.schemas.band import BandOut, BandLookupOut
from app.services.band_service import BandService

router = APIRouter(prefix="/bands", tags=["bands"])


@router.get("", response_model=List[BandOut])
async def list_bands(
    db: AsyncSession = Depends(get_db),
    current_user: AllowedUser = Depends(get_current_user),
):
    return await BandService.list_all(db)


@router.get("/resolve", response_model=BandLookupOut)
async def resolve_designation(
    stream: str = Query(...),
    band: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: AllowedUser = Depends(get_current_user),
):
    return await BandService.resolve(db, stream, band)

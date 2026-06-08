from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from app.models.band import BandDesignation


class BandService:
    @staticmethod
    async def list_all(db: AsyncSession) -> list[BandDesignation]:
        result = await db.execute(
            select(BandDesignation).order_by(BandDesignation.stream, BandDesignation.band)
        )
        return result.scalars().all()

    @staticmethod
    async def resolve(db: AsyncSession, stream: str, band: str) -> dict:
        result = await db.execute(
            select(BandDesignation).where(
                BandDesignation.stream == stream,
                BandDesignation.band == band,
            )
        )
        rows = result.scalars().all()
        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"No designation found for stream={stream}, band={band}",
            )
        return {
            "stream": stream,
            "band": band,
            "designations": [r.designation for r in rows],
        }

    @staticmethod
    async def get_designation(db: AsyncSession, stream: str, band: str) -> str | None:
        result = await db.execute(
            select(BandDesignation).where(
                BandDesignation.stream == stream,
                BandDesignation.band == band,
            )
        )
        row = result.scalar_one_or_none()
        return row.designation if row else None

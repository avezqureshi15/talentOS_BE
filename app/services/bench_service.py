"""
Webtrack integration — read-only PostgreSQL.
Queries employee bench availability for a given stream + band.
Schema will be confirmed once Webtrack schema is shared.
"""
from typing import Optional
from app.core.config import settings

_webtrack_engine = None


def get_webtrack_engine():
    global _webtrack_engine
    if _webtrack_engine is None and settings.WEBTRACK_DATABASE_URL:
        from sqlalchemy.ext.asyncio import create_async_engine
        _webtrack_engine = create_async_engine(
            settings.WEBTRACK_DATABASE_URL,
            pool_size=3,
            max_overflow=5,
        )
    return _webtrack_engine


class BenchService:
    @staticmethod
    async def check_bench(stream: str, band: str) -> list[dict]:
        """
        Query Webtrack for employees on bench matching stream + band.
        Returns list of employee dicts.
        TODO: update query once Webtrack schema is confirmed.
        """
        engine = get_webtrack_engine()
        if not engine:
            # Webtrack not configured yet — return stub
            return []

        from sqlalchemy import text
        async with engine.connect() as conn:
            # TODO: replace with actual Webtrack table/column names
            result = await conn.execute(
                text("""
                    SELECT id, name, email, designation, band, stream, status
                    FROM employees
                    WHERE stream = :stream
                      AND band = :band
                      AND status = 'bench'
                    ORDER BY name
                """),
                {"stream": stream, "band": band},
            )
            rows = result.mappings().all()
            return [dict(row) for row in rows]

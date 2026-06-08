from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import engine, Base
from app.routers import auth, admin, chat, jobs, applications, candidates, bands, audit, notifications


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — tables created via Alembic in prod, auto-create for dev
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(
    title="TalentOS API",
    description="Webknot TalentOS Recruitment Platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(chat.router)
app.include_router(jobs.router)
app.include_router(applications.router)
app.include_router(candidates.router)
app.include_router(bands.router)
app.include_router(audit.router)
app.include_router(notifications.router)


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME}

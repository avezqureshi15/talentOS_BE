from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # App
    APP_NAME: str = "TalentOS"
    DEBUG: bool = False
    FRONTEND_URL: str = "http://localhost:3000"

    # Database
    DATABASE_URL: str  # postgresql+asyncpg://user:pass@host/db

    # Redis + Celery
    REDIS_URL: str = "redis://localhost:6379/0"

    # Google OAuth
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"

    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 8  # 8 hours

    # Anthropic
    ANTHROPIC_API_KEY: str

    # Webtrack (read-only PostgreSQL)
    WEBTRACK_DATABASE_URL: str = ""

    # Careers Page (Supabase)
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

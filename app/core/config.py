from pydantic import model_validator
from pydantic_settings import BaseSettings

_DEV_TIMING = {
    "FORM_REMINDER_HOURS": 0.002778,
    "FORM_ESCALATION_HOURS": 0.005556,
    "FORM_EXPIRY_HOURS": 24,
    "AI_ROUND_EVALUATION_DELAY_MINUTES": 1,
}

_PROD_TIMING = {
    "FORM_REMINDER_HOURS": 2,
    "FORM_ESCALATION_HOURS": 3,
    "FORM_EXPIRY_HOURS": 24,
    "AI_ROUND_EVALUATION_DELAY_MINUTES": 0,
}


class Settings(BaseSettings):
    DATABASE_URL: str
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    APP_NAME: str = "talentOS API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    SUPABASE_FUNCTIONS_BASE_URL: str = ""
    RESEND_API_KEY: str = ""

    SERVICE_NAME: str = "talentos-be"

    JWKS_URL_AI_RECRUITMENT_POC: str = ""

    # ai-recruitment-poc (RH) integration
    RH_SERVICE_URL: str = ""
    RH_SERVICE_PRIVATE_KEY_PATH: str = ""

    # Supabase webhook verification (shared secret sent as X-Webhook-Secret header).
    # When empty, verification is skipped (local dev only — set this in prod).
    SUPABASE_WEBHOOK_SECRET: str = ""
    # Service-role key for downloading resumes from private Supabase Storage buckets.
    # Leave empty if the resume bucket is public.
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    # Kafka / Redpanda
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_TOPIC_EVALUATION_ASYNC: str = "resume.evaluation.async"
    KAFKA_TOPIC_EVALUATION_ASYNC_DLQ: str = "resume.evaluation.async.dlq"
    KAFKA_EVALUATION_PARTITIONS: int = 6

    # talentOS_AI resume evaluation service
    AI_SERVICE_BASE_URL: str = ""
    AI_SERVICE_TIMEOUT: int = 60

    # Resume evaluation processing
    ATS_THRESHOLD_DEFAULT: int = 70
    EVALUATION_MAX_ATTEMPTS: int = 3
    EVALUATION_MIN_RESUME_CHARS: int = 100

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # Google Calendar (service account + domain-wide delegation)
    GOOGLE_SERVICE_ACCOUNT_JSON: str = ""
    GOOGLE_IMPERSONATION_EMAIL: str = ""
    GOOGLE_CALENDAR_TIMEZONE: str = "Asia/Kolkata"

    # Auth
    ALLOWED_EMAIL_DOMAIN: str = ""

    # CORS
    CORS_ALLOW_ORIGINS: str = "http://localhost:5173,http://localhost:4173,http://localhost:5175,http://localhost:5174"

    # JWT
    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # SMTP / Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    FRONTEND_BASE_URL: str = "http://localhost:5173"

    # Form timing — prod defaults; overridden for dev via model_validator
    FORM_REMINDER_HOURS: float = 2
    FORM_ESCALATION_HOURS: float = 3
    FORM_EXPIRY_HOURS: float = 24

    AI_ROUND_EVALUATION_DELAY_MINUTES: int = 0

    @model_validator(mode="after")
    def _apply_env_timing(self) -> "Settings":
        timing = _DEV_TIMING if self.APP_ENV == "development" else _PROD_TIMING
        self.FORM_REMINDER_HOURS = timing["FORM_REMINDER_HOURS"]
        self.FORM_ESCALATION_HOURS = timing["FORM_ESCALATION_HOURS"]
        self.FORM_EXPIRY_HOURS = timing["FORM_EXPIRY_HOURS"]
        self.AI_ROUND_EVALUATION_DELAY_MINUTES = timing["AI_ROUND_EVALUATION_DELAY_MINUTES"]
        return self

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "case_sensitive": True}


settings = Settings()

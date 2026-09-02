import logging
import os

from dotenv import load_dotenv
from pydantic import model_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

# Settings fields the app pulls from OpenBao at startup (comma-separated).
# Override with BAO_SECRET_KEYS. OpenBao values win over .env.
_DEFAULT_BAO_KEYS = (
    "JWT_SECRET,SECRETS_ENCRYPTION_KEY,DATABASE_URL,RESEND_API_KEY,"
    "SMTP_USERNAME,SMTP_PASSWORD,GOOGLE_CLIENT_SECRET,"
    "GOOGLE_SERVICE_ACCOUNT_JSON,GOOGLE_IMPERSONATION_EMAIL,"
    "MEETMIND_API_TOKEN,MEETMIND_WEBHOOK_SECRET,"
    "SUPABASE_SERVICE_ROLE_KEY,SUPABASE_WEBHOOK_SECRET,"
    "RH_API_KEY,SERVICE_API_KEY"
)

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
    # Timezone for log line timestamps (e.g. Asia/Kolkata for IST).
    # DB timestamps and API payloads remain UTC regardless of this.
    LOG_TIMEZONE: str = "Asia/Kolkata"
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
    RH_API_KEY: str = ""
    SERVICE_API_KEY: str = ""

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
    KAFKA_TOPIC_INTERVIEW_REPORT_ASYNC: str = "ai.interview.report.async"
    KAFKA_TOPIC_INTERVIEW_REPORT_ASYNC_DLQ: str = "ai.interview.report.async.dlq"
    KAFKA_INTERVIEW_REPORT_PARTITIONS: int = 6

    # talentOS_AI resume evaluation service
    AI_SERVICE_BASE_URL: str = ""
    AI_SERVICE_TIMEOUT: int = 60

    # Resume evaluation processing
    ATS_THRESHOLD_DEFAULT: int = 70
    EVALUATION_MAX_ATTEMPTS: int = 3
    EVALUATION_MIN_RESUME_CHARS: int = 100

    # AI interview report transform
    INTERVIEW_REPORT_MAX_TRANSCRIPT_CHARS: int = 150_000
    INTERVIEW_REPORT_MAX_ATTEMPTS: int = 3

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # Google Calendar (service account + domain-wide delegation)
    GOOGLE_SERVICE_ACCOUNT_JSON: str = ""
    GOOGLE_IMPERSONATION_EMAIL: str = ""
    GOOGLE_CALENDAR_TIMEZONE: str = "Asia/Kolkata"

    # Auth
    ALLOWED_EMAIL_DOMAIN: str = ""
    ALLOW_SIGNUP: bool = False

    # CORS
    CORS_ALLOW_ORIGINS: str = (
        "http://localhost:5173,http://localhost:4173,http://localhost:5174,http://localhost:5175,"
        "http://127.0.0.1:5173,http://127.0.0.1:4173,http://127.0.0.1:5174,http://127.0.0.1:5175"
    )

    # JWT
    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Data-encryption key for tenant-managed API secrets (Fernet).
    # Falls back to JWT_SECRET when unset.
    SECRETS_ENCRYPTION_KEY: str = ""

    # OpenBao (central secrets manager). When BAO_ADDR + a token are present,
    # the _DEFAULT_BAO_KEYS secrets are fetched from OpenBao at startup and
    # override the .env values. In local dev leave BAO_ADDR empty to fall back
    # to environment values.
    BAO_ADDR: str = ""
    BAO_TOKEN: str = ""
    BAO_TOKEN_FILE: str = ""
    BAO_KV_MOUNT: str = "secret"
    BAO_KV_PATH: str = "talentos"
    BAO_REQUIRED: bool = False
    BAO_SECRET_KEYS: str = ""

    # SMTP / Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    FRONTEND_BASE_URL: str = ""

    # Form timing — prod defaults; overridden for dev via model_validator
    FORM_REMINDER_HOURS: float = 2
    FORM_ESCALATION_HOURS: float = 3
    FORM_EXPIRY_HOURS: float = 24

    # MeetMind integration (schedule + signed transcript webhook)
    MEETMIND_BASE_URL: str = ""
    MEETMIND_API_TOKEN: str = ""
    MEETMIND_WEBHOOK_SECRET: str = ""
    MEETMIND_EXTERNAL: str = "talentos.ai"
    INTERVIEW_FALLBACK_SECONDS: int = 60
    AI_ROUND_EVALUATION_DELAY_MINUTES: int = 0

    @model_validator(mode="after")
    def _apply_env_timing(self) -> "Settings":
        timing = (
            _DEV_TIMING
            if self.APP_ENV in ("development", "uat", "staging")
            else _PROD_TIMING
        )
        for key, value in timing.items():
            # Explicitly-set env vars (FORM_REMINDER_HOURS etc.) override the
            # APP_ENV defaults; unset fields fall back to the env's timing.
            if key not in self.model_fields_set:
                setattr(self, key, value)
        return self

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "case_sensitive": True}


# Load the local .env into the environment so the OpenBao bootstrap vars
# (BAO_ADDR / BAO_TOKEN_FILE) are visible before Settings() is built.
load_dotenv()


_BAO_LOADED_FLAG = "BAO_SECRETS_LOADED"


def _inject_openbao_secrets() -> None:
    """Fetch secrets from OpenBao and inject them into os.environ.

    Runs BEFORE ``Settings()`` is constructed so required fields with no
    default (e.g. DATABASE_URL) resolve from OpenBao exactly like env vars.
    No-op when BAO_ADDR is empty (local dev without OpenBao).

    ``uvicorn --reload`` (especially on Windows spawn) imports this module
    twice: the parent fetch can succeed, then the worker fetch gets 403 and
    would otherwise crash despite secrets already sitting in ``os.environ``.
    """
    addr = os.environ.get("BAO_ADDR", "").strip()
    if not addr:
        return

    # Local import: avoids a circular import (config -> openbao -> logger -> config).
    from app.core.openbao import fetch_secrets

    keys = [
        k.strip()
        for k in os.environ.get("BAO_SECRET_KEYS", _DEFAULT_BAO_KEYS).split(",")
        if k.strip()
    ]
    # DATABASE_URL is required and only comes from OpenBao in local-dev .env,
    # so it is a reliable signal that a parent --reload process already injected.
    injected = bool(os.environ.get("DATABASE_URL", "").strip())
    if os.environ.get(_BAO_LOADED_FLAG, "").lower() in ("1", "true", "yes") and injected:
        logger.info("Skipping OpenBao fetch; secrets already loaded in this process env")
        return

    fetched = fetch_secrets(keys)
    if not fetched and os.environ.get("BAO_REQUIRED", "").lower() in ("1", "true", "yes"):
        if injected:
            logger.warning(
                "OpenBao fetch from %s returned nothing; reusing secrets already in env "
                "(typical with uvicorn --reload)",
                addr,
            )
        else:
            raise RuntimeError(
                f"OpenBao is required (BAO_REQUIRED=true) but no secrets could be fetched from {addr}. "
                "HTTP 403 usually means this machine's public IP is not in BAO_TOKEN_ALLOWED_IPS "
                "on the server; HTTP 404 means the KV path (BAO_KV_PATH) has no such key."
            )
    for key, value in fetched.items():
        os.environ[key] = value
    if fetched:
        os.environ[_BAO_LOADED_FLAG] = "1"
        logger.info("Loaded %d/%d secrets from OpenBao at %s", len(fetched), len(keys), addr)
    else:
        logger.warning("No secrets loaded from OpenBao at %s — using environment values", addr)


_inject_openbao_secrets()

settings = Settings()

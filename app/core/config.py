from pydantic_settings import BaseSettings


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

    # Supabase webhook verification (shared secret sent as X-Webhook-Secret header).
    # When empty, verification is skipped (local dev only — set this in prod).
    SUPABASE_WEBHOOK_SECRET: str = ""
    # Service-role key for downloading resumes from private Supabase Storage buckets.
    # Leave empty if the resume bucket is public.
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    # Kafka / Redpanda
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_TOPIC_EVALUATION: str = "resume.evaluation.queue"
    KAFKA_TOPIC_EVALUATION_DLQ: str = "resume.evaluation.dlq"
    KAFKA_CONSUMER_GROUP: str = "resume-evaluators"
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

    # Auth
    ALLOWED_EMAIL_DOMAIN: str = ""

    # JWT
    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "case_sensitive": True}


settings = Settings()

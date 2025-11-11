from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Load order:
    1. Environment variables (highest priority)
    2. .env file in project root
    3. Field defaults (lowest priority)
    """

    # ✅ Correct Pydantic v2 config
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/jewelry_db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    # OpenAI
    openai_api_key: str = ""

    # Application
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    # Storage
    image_storage_path: str = "./data/images"
    max_images_per_product: int = 5

    # Crawler
    crawler_max_pages: int = 100
    crawler_timeout: int = 60000
    crawler_headless: bool = True
    crawler_user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )

    # AI
    ai_model: str = "gpt-4o"
    ai_max_tokens: int = 500
    ai_temperature: float = 0.3

    # Processing Limits (for cost control during development)
    max_products_to_process: int = 10

    # ✅ Email Notifications (loaded from .env)
    email_enabled: bool = True
    email_host: str = "smtp.gmail.com"
    email_port: int = 587
    email_host_user: str = "ai.skinanalyser@gmail.com"
    email_host_password: str = ""
    email_use_tls: bool = True
    email_from: str = "ai.skinanalyser@gmail.com"
    email_to: str = "bharathsethu18@gmail.com"

    # Optional S3
    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    s3_access_key: str = ""
    s3_secret_key: str = ""


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()

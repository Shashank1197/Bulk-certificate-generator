from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings."""

    PROJECT_NAME: str = "Bulk Certificate Generator API"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = (
        "High-performance REST API for bulk certificate generation, validation, "
        "asynchronous processing, status tracking, and multi-format certificate retrieval."
    )
    API_V1_STR: str = "/api/v1"

    # Database configuration (Defaults to local SQLite, easily overridden with PostgreSQL)
    DATABASE_URL: str = "sqlite:///./certificates.db"

    # Storage paths
    STORAGE_DIR: Path = Path("storage/certificates")

    # Base application URL for generating verification and download hyperlinks
    BASE_URL: str = "http://localhost:8000"

    # Batch limits
    MAX_RECIPIENTS_PER_JOB: int = 5000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

# Ensure storage directory exists
settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)

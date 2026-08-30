"""
DRISHTI Backend — Application Configuration

Reads environment variables using Pydantic Settings.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: str = "development"
    app_debug: bool = True

    # Database
    database_url: str = "postgresql://drishti:drishti@localhost:5432/drishti"

    # CORS
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://192.168.29.207:3000",
    ]

    # OCR Limits
    max_upload_size_mb: int = 10
    allowed_mime_types: list[str] = ["image/jpeg", "image/png"]

    # Optional Gemini package understanding (advisory observations only)
    gemini_enabled: bool = False
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.7-flash"
    gemini_timeout_seconds: float = 12.0
    gemini_context_min_confidence: float = 0.75

    # MinIO / S3 Object Storage
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_bucket_name: str = "drishti-captures"
    minio_secure: bool = False

    # Authentication & JWT
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    # Optional Bootstrap Admin (loaded via environment)
    admin_bootstrap_username: str = ""
    admin_bootstrap_password: str = ""
    admin_bootstrap_email: str = ""


settings = Settings()

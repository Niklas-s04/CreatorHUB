from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "creator-suite"
    ENV: str = "prod"

    DATABASE_URL: str = "postgresql+psycopg://creator:creator@localhost:5432/creator_suite"

    JWT_SECRET: str = Field(..., min_length=32)
    JWT_ACCESS_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_EXPIRE_MINUTES: int = 60 * 24 * 14

    UPLOADS_DIR: str = "/data/uploads"
    CACHE_DIR: str = "/data/cache"
    EXPORTS_DIR: str = "/data/exports"

    REDIS_URL: str = "redis://localhost:6379/0"

    OLLAMA_URL: str = "http://localhost:11434"
    OLLAMA_TEXT_MODEL: str = "llama3.1:8b"
    OLLAMA_VISION_MODEL: str = "llava:latest"

    # Standardquellen für die Bildsuche ohne API-Schlüssel.
    # Kommagetrennte Liste für source="auto".
    IMAGE_HUNT_DEFAULT_SOURCES: str = "wikimedia,openverse"

    # Openverse-Basis-URL ohne API-Schlüssel.
    OPENVERSE_API_BASE: str = "https://api.openverse.engineering/v1"

    CORS_ORIGINS: str = "http://localhost:3000"
    TRUSTED_HOSTS: str = "localhost,127.0.0.1"
    MAX_REQUEST_BODY_BYTES: int = 2_000_000
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RATE_LIMIT_GLOBAL: int = 240
    RATE_LIMIT_AUTH: int = 10
    RATE_LIMIT_REDIS_PREFIX: str = "rl"
    TRUST_PROXY_HEADERS: bool = False
    SECURITY_HSTS_SECONDS: int = 31536000
    AUTH_COOKIE_NAME: str = "creatorhub_auth"
    AUTH_ACCESS_COOKIE_NAME: str = "creatorhub_access"
    AUTH_REFRESH_COOKIE_NAME: str = "creatorhub_refresh"
    AUTH_COOKIE_SECURE: bool = True
    AUTH_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "strict"
    AUTH_COOKIE_DOMAIN: str | None = None
    AUTH_ACCESS_COOKIE_MAX_AGE_SECONDS: int = 60 * 15
    AUTH_REFRESH_COOKIE_MAX_AGE_SECONDS: int = 60 * 60 * 24 * 14
    AUTH_COOKIE_MAX_AGE_SECONDS: int = 60 * 60 * 24 * 14
    CSRF_COOKIE_NAME: str = "creatorhub_csrf"

    SESSION_IDLE_TIMEOUT_MINUTES: int = 60
    SESSION_ABSOLUTE_TIMEOUT_MINUTES: int = 60 * 24 * 30

    AUTH_MAX_FAILED_ATTEMPTS: int = 5
    AUTH_LOCK_MINUTES: int = 30
    AUTH_SUSPICIOUS_FAILED_THRESHOLD: int = 5
    AUTH_SUSPICIOUS_WINDOW_MINUTES: int = 15

    MFA_TOTP_ISSUER: str = "CreatorHUB"
    MFA_RECOVERY_CODES_COUNT: int = 8

    SECURITY_SENSITIVE_ACTION_CONFIRMATION_REQUIRED: bool = False
    SECURITY_SENSITIVE_ACTION_CONFIRMATION_HEADER: str = "x-action-confirm"
    SECURITY_SENSITIVE_ACTION_CONFIRMATION_VALUE: str = "CONFIRM"
    SECURITY_SENSITIVE_ACTION_REQUIRE_STEP_UP_MFA: bool = False

    PASSWORD_RESET_TOKEN_TTL_MINUTES: int = 30

    OUTBOUND_CONNECT_TIMEOUT_SECONDS: int = 5
    OUTBOUND_READ_TIMEOUT_SECONDS: int = 20
    OUTBOUND_MAX_RESPONSE_BYTES: int = 8 * 1024 * 1024
    OUTBOUND_MAX_REDIRECTS: int = 2
    OUTBOUND_RETRIES: int = 1
    OUTBOUND_ALLOWED_PORTS: str = "443"
    OUTBOUND_REQUIRE_HTTPS: bool = True
    OUTBOUND_ALLOWLIST_HOSTS: str = ""
    OUTBOUND_SENSITIVE_ALLOWLIST_HOSTS: str = ""
    OUTBOUND_BLOCK_PRIVATE_RANGES: bool = True

    UPLOAD_ALLOWED_IMAGE_EXTENSIONS: str = ".jpg,.jpeg,.png,.webp,.gif"
    UPLOAD_ALLOWED_PDF_EXTENSIONS: str = ".pdf"
    UPLOAD_MAX_IMAGE_BYTES: int = 8 * 1024 * 1024
    UPLOAD_MAX_PDF_BYTES: int = 15 * 1024 * 1024
    UPLOAD_MAX_IMAGE_WIDTH: int = 8000
    UPLOAD_MAX_IMAGE_HEIGHT: int = 8000
    UPLOAD_MAX_IMAGE_PIXELS: int = 30_000_000
    ASSET_MAX_DELIVERY_BYTES: int = 25 * 1024 * 1024
    ENABLE_OPTIONAL_MALWARE_SCAN: bool = False

    BOOTSTRAP_ADMIN_USERNAME: str = "admin"
    BOOTSTRAP_ADMIN_PASSWORD: str = Field(..., min_length=12)
    BOOTSTRAP_INSTALL_TOKEN: str = ""

    AUTO_ARCHIVE_ENABLED: bool = True
    AUTO_ARCHIVE_INTERVAL_MINUTES: int = 720  # Standard: zweimal täglich
    AUTO_ARCHIVE_SOLD_AFTER_DAYS: int = 30

    LOG_LEVEL: str = "INFO"
    UVICORN_LOG_LEVEL: str = "INFO"
    UVICORN_ACCESS_LOG_LEVEL: str = "WARNING"
    LOG_FORMAT: Literal["json", "plain"] = "json"
    LOG_TO_STDOUT: bool = True
    LOG_TO_FILE: bool = False
    LOG_DIR: str = "/data/logs"
    LOG_FILE_NAME: str = "application.log"
    LOG_RETENTION_DAYS: int = 30

    SECURITY_LOG_LEVEL: str = "WARNING"
    SECURITY_LOG_TO_SEPARATE_FILE: bool = True
    SECURITY_LOG_FILE_NAME: str = "security-events.log"
    SECURITY_LOG_RETENTION_DAYS: int = 90
    SECURITY_LOG_PROPAGATE_TO_ROOT: bool = True

    OBSERVABILITY_METRICS_ENABLED: bool = True
    OBSERVABILITY_METRICS_PATH: str = "/health/metrics"
    OBSERVABILITY_MONITOR_ENABLED: bool = True
    OBSERVABILITY_MONITOR_INTERVAL_SECONDS: int = 30

    ALERT_DB_FAILURE_CONSECUTIVE: int = 3
    ALERT_REDIS_FAILURE_CONSECUTIVE: int = 3
    ALERT_WORKER_FAILURE_CONSECUTIVE: int = 3
    ALERT_QUEUE_LENGTH_WARN: int = 100
    ALERT_QUEUE_LENGTH_CRITICAL: int = 500
    ALERT_FAILED_JOBS_CRITICAL: int = 20

    OTEL_ENABLED: bool = False
    OTEL_SERVICE_NAME: str = "creatorhub-backend"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = ""
    OTEL_EXPORTER_OTLP_INSECURE: bool = True
    OTEL_SAMPLE_RATIO: float = 0.2


settings = Settings()

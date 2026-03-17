from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "creator-suite"
    ENV: str = "prod"

    DATABASE_URL: str = "postgresql+psycopg://creator:creator@localhost:5432/creator_suite"

    JWT_SECRET: str = "change_me"
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
    AUTH_COOKIE_SECURE: bool = False
    AUTH_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
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

    PASSWORD_RESET_TOKEN_TTL_MINUTES: int = 30

    BOOTSTRAP_ADMIN_USERNAME: str = "admin"
    BOOTSTRAP_ADMIN_PASSWORD: str = "admin"

    AUTO_ARCHIVE_ENABLED: bool = True
    AUTO_ARCHIVE_INTERVAL_MINUTES: int = 720  # Standard: zweimal täglich
    AUTO_ARCHIVE_SOLD_AFTER_DAYS: int = 30


settings = Settings()
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "creator-suite"
    ENV: str = "prod"

    DATABASE_URL: str = "postgresql+psycopg://creator:creator@localhost:5432/creator_suite"

    JWT_SECRET: str = "change_me"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 Tage

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

    BOOTSTRAP_ADMIN_USERNAME: str = "admin"
    BOOTSTRAP_ADMIN_PASSWORD: str = "admin"

    AUTO_ARCHIVE_ENABLED: bool = True
    AUTO_ARCHIVE_INTERVAL_MINUTES: int = 720  # Standard: zweimal täglich
    AUTO_ARCHIVE_SOLD_AFTER_DAYS: int = 30


settings = Settings()
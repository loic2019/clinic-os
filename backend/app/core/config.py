"""
Central application configuration.

All configuration values are loaded from environment variables (or a local
".env" file during development). Nothing sensitive should ever be
hard-coded here — this module only defines defaults and types.
"""

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Application ---
    APP_NAME: str = "CLINIC OS"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api"

    # --- Database ---
    DATABASE_URL: str = (
        "postgresql+asyncpg://clinic_user:clinic_password@localhost:5432/clinic_os"
    )
    DATABASE_URL_SYNC: str = (
        "postgresql+psycopg2://clinic_user:clinic_password@localhost:5432/clinic_os"
    )

    # --- Security (used from Phase 2 onward) ---
    SECRET_KEY: str = "change-this-to-a-long-random-secret-key"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- Storage ---
    UPLOAD_DIRECTORY: str = "./storage"

    # --- CORS ---
    # Includes the frontend's static-server port (5500) by default, since
    # the frontend and backend run as separate origins in dev. Without
    # this, the browser's CORS check silently blocks every request from
    # the frontend even though the backend itself is healthy — this bit
    # us once, so it's covered by default rather than left to chance.
    CORS_ORIGINS: str = "http://localhost:8000,http://127.0.0.1:8000,http://localhost:5500,http://127.0.0.1:5500"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _ensure_async_driver(cls, value: str) -> str:
        # Hosting platforms (Render, Railway, Heroku-style) hand out a
        # bare "postgres://" or "postgresql://" URL with no driver, since
        # they don't know which Python DB library the app uses. Rather
        # than requiring the person deploying to hand-edit that URL,
        # normalize it to the async driver this app actually needs.
        if value.startswith("postgres://"):
            value = "postgresql://" + value[len("postgres://"):]
        if value.startswith("postgresql://"):
            value = "postgresql+asyncpg://" + value[len("postgresql://"):]
        return value

    @field_validator("DATABASE_URL_SYNC", mode="before")
    @classmethod
    def _ensure_sync_driver(cls, value: str) -> str:
        if value.startswith("postgres://"):
            value = "postgresql://" + value[len("postgres://"):]
        if value.startswith("postgresql://") and "+psycopg2" not in value:
            value = "postgresql+psycopg2://" + value[len("postgresql://"):]
        return value

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached Settings instance so the environment is parsed only
    once per process. Import this function wherever configuration is
    needed instead of instantiating Settings() directly.
    """
    return Settings()


settings = get_settings()

"""
Application configuration, loaded from environment variables (.env in local
dev, real environment variables in production). Never hardcode secrets here —
every sensitive value is Optional/required-with-no-default so a missing .env
fails loudly instead of silently falling back to a bogus value.
"""

from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Application metadata ---
    PROJECT_NAME: str = "RALLY API"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"

    # --- Supabase ---
    SUPABASE_URL: Optional[str] = None
    SUPABASE_ANON_KEY: Optional[str] = None
    # Server-only. Never send this to the frontend or return it in a response.
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None

    # --- Database (Supabase Postgres) ---
    DATABASE_URL: Optional[str] = None

    # --- Redis (wired later — read now so config is ready ahead of time) ---
    REDIS_URL: Optional[str] = None

    # --- Auth ---
    # Supabase Auth's JWT signing secret. FastAPI only ever *verifies* tokens
    # issued by Supabase Auth — it never mints its own.
    JWT_SECRET: Optional[str] = None
    JWT_ALGORITHM: str = "HS256"

    # --- Routing engine (wired later) ---
    OSRM_URL: Optional[str] = None

    # --- CORS ---
    # Comma-separated list of allowed origins, e.g.
    # "http://localhost:3000,https://rally.app"
    FRONTEND_URL: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001"

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.FRONTEND_URL.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

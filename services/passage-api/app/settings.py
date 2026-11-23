from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All config comes from env vars (names are case-insensitive)."""

    db_connection_string: str = ""
    db_create_if_missing: bool = False  # true only in docker-compose (local SQL Server)
    cors_origin: str = "http://localhost:8080"
    log_level: str = "INFO"
    conditions_api_url: str = "http://localhost:8002"
    conditions_timeout_s: float = 3.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
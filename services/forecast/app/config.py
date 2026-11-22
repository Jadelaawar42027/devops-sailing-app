"""Configuration, read only from environment variables (brief §4)."""

import os
from dataclasses import dataclass

from sqlalchemy.engine import URL

ODBC_DRIVER = "ODBC Driver 18 for SQL Server"


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    service_name: str = "forecast"
    version: str = "dev"
    log_level: str = "INFO"
    cors_origins: tuple[str, ...] = ("http://localhost:8090",)
    database_url: str | URL = "sqlite:///./local.db"
    db_create_if_missing: bool = False
    db_connect_retries: int = 20
    db_retry_delay_s: float = 5.0
    run_migrations: bool = True
    # Open-Meteo (free, no API key). Wind from the weather API, waves from the Marine API.
    weather_url: str = "https://api.open-meteo.com/v1/forecast"
    marine_url: str = "https://marine-api.open-meteo.com/v1/marine"
    upstream_timeout_s: float = 4.0
    forecast_ttl_s: int = 1800  # hourly forecasts change slowly: 30 min cache
    current_ttl_s: int = 600  # current conditions: 10 min cache
    forecast_days: int = 3


def database_url_from_env() -> str | URL:
    """DATABASE_URL wins; otherwise build an Azure SQL / SQL Server URL from DB_* variables."""
    if os.getenv("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    host = os.getenv("DB_HOST")
    if not host:
        return "sqlite:///./local.db"
    return URL.create(
        "mssql+pyodbc",
        username=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=host,
        port=int(os.getenv("DB_PORT", "1433")),
        database=os.getenv("DB_NAME", "forecast"),
        query={
            "driver": ODBC_DRIVER,
            "Encrypt": "yes",
            "TrustServerCertificate": "yes" if _bool(os.getenv("DB_TRUST_CERT")) else "no",
        },
    )


def load_settings() -> Settings:
    return Settings(
        version=os.getenv("APP_VERSION", "dev"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        cors_origins=tuple(_csv(os.getenv("CORS_ORIGINS", "http://localhost:8090"))),
        database_url=database_url_from_env(),
        db_create_if_missing=_bool(os.getenv("DB_CREATE_IF_MISSING")),
        db_connect_retries=int(os.getenv("DB_CONNECT_RETRIES", "20")),
        db_retry_delay_s=float(os.getenv("DB_RETRY_DELAY_S", "5")),
        weather_url=os.getenv("OPEN_METEO_WEATHER_URL", Settings.weather_url),
        marine_url=os.getenv("OPEN_METEO_MARINE_URL", Settings.marine_url),
        upstream_timeout_s=float(os.getenv("UPSTREAM_TIMEOUT_S", "4")),
        forecast_ttl_s=int(os.getenv("FORECAST_TTL_S", "1800")),
        current_ttl_s=int(os.getenv("CURRENT_TTL_S", "600")),
    )

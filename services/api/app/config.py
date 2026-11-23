"""Configuration, read only from environment variables (brief §4)."""

import os
from dataclasses import dataclass


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    service_name: str = "api"
    version: str = "dev"
    log_level: str = "INFO"
    cors_origins: tuple[str, ...] = ("http://localhost:8090",)


def load_settings() -> Settings:
    return Settings(
        version=os.getenv("APP_VERSION", "dev"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        cors_origins=tuple(_csv(os.getenv("CORS_ORIGINS", "http://localhost:8090"))),
    )

"""Database engine, sessions and migrations-on-startup (brief §3a: versioned migrations)."""

import logging
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

from alembic import command
from alembic.config import Config
from fastapi import Depends, Request
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings

log = logging.getLogger(__name__)
MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def make_engine(url: str | URL) -> Engine:
    url = make_url(url)
    if url.get_backend_name() == "sqlite":
        kwargs = {"connect_args": {"check_same_thread": False}}
        if url.database in (None, "", ":memory:"):
            kwargs["poolclass"] = StaticPool
        return create_engine(url, **kwargs)
    # pool_pre_ping: Azure SQL serverless auto-pauses; drop dead connections instead of failing.
    return create_engine(url, pool_pre_ping=True, pool_recycle=1800)


def create_database_if_missing(url: str | URL) -> None:
    """Local compose only: SQL Server starts empty, so create the service's database."""
    url = make_url(url)
    if url.get_backend_name() != "mssql":
        return
    name = url.database
    master = create_engine(url.set(database="master"), isolation_level="AUTOCOMMIT")
    try:
        with master.connect() as conn:
            conn.execute(text(f"IF DB_ID(N'{name}') IS NULL CREATE DATABASE [{name}]"))
    finally:
        master.dispose()


def run_migrations(engine: Engine) -> None:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    with engine.begin() as connection:
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "head")


def prepare_database(settings: Settings, engine: Engine) -> None:
    """Create (local only) and migrate the database, retrying while it wakes up."""
    for attempt in range(1, settings.db_connect_retries + 1):
        try:
            if settings.db_create_if_missing:
                create_database_if_missing(settings.database_url)
            run_migrations(engine)
            log.info("migrations applied", extra={"fields": {"attempt": attempt}})
            return
        except Exception as exc:  # any DB error during startup is retried
            if attempt == settings.db_connect_retries:
                raise
            log.warning(
                "database not ready, retrying",
                extra={"fields": {"attempt": attempt, "error": type(exc).__name__}},
            )
            time.sleep(settings.db_retry_delay_s)


def get_session(request: Request) -> Iterator[Session]:
    factory: sessionmaker[Session] = request.app.state.session_factory
    with factory() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]

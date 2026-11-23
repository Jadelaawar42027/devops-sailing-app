"""Versioned SQL migrations, applied on startup.

migrations/NNN_description.sql files are applied in order. Each applied version is
recorded in schema_version, so a fresh DB gets all of them and an existing DB only
gets the new ones. Running it twice is a no-op.
"""

import logging
import re
from pathlib import Path

from app.db import connect_with_retry, parse_connection_string

logger = logging.getLogger("passage-api.migrations")

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
FILENAME_RE = re.compile(r"^(\d{3})_[\w-]+\.sql$")


def discover(directory: Path = MIGRATIONS_DIR) -> list[tuple[int, Path]]:
    found = []
    for path in directory.glob("*.sql"):
        match = FILENAME_RE.match(path.name)
        if not match:
            raise ValueError(f"Bad migration filename: {path.name} (expected NNN_name.sql)")
        found.append((int(match.group(1)), path))
    found.sort()
    versions = [v for v, _ in found]
    if len(versions) != len(set(versions)):
        raise ValueError(f"Duplicate migration versions: {versions}")
    return found


def pending(applied: set[int], available: list[tuple[int, Path]]) -> list[tuple[int, Path]]:
    return [(v, p) for v, p in available if v not in applied]


def ensure_database(conn_str: str) -> None:
    """Local only: the SQL Server container starts with just `master`."""
    db_name = parse_connection_string(conn_str)["database"]
    if not re.fullmatch(r"[A-Za-z0-9_-]+", db_name):
        raise ValueError(f"Unsafe database name: {db_name!r}")
    conn = connect_with_retry(conn_str, database="master", autocommit=True)
    try:
        cur = conn.cursor()
        cur.execute(f"IF DB_ID(N'{db_name}') IS NULL CREATE DATABASE [{db_name}]")
    finally:
        conn.close()


def run_migrations(conn_str: str, create_db: bool = False) -> list[int]:
    if create_db:
        ensure_database(conn_str)

    conn = connect_with_retry(conn_str)
    try:
        cur = conn.cursor()
        cur.execute(
            "IF OBJECT_ID(N'schema_version', N'U') IS NULL "
            "CREATE TABLE schema_version ("
            "  version INT NOT NULL PRIMARY KEY,"
            "  filename NVARCHAR(255) NOT NULL,"
            "  applied_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME())"
        )
        conn.commit()

        cur.execute("SELECT version FROM schema_version")
        applied = {row[0] for row in cur.fetchall()}

        done = []
        for version, path in pending(applied, discover()):
            logger.info("Applying migration %s", path.name)
            try:
                cur.execute(path.read_text(encoding="utf-8"))
                cur.execute(
                    "INSERT INTO schema_version (version, filename) VALUES (%d, %s)",
                    (version, path.name),
                )
                conn.commit()  # one transaction per file
            except Exception:
                conn.rollback()
                logger.exception("Migration %s failed, rolled back", path.name)
                raise
            done.append(version)

        logger.info("Migrations up to date (applied now: %s)", done or "none")
        return done
    finally:
        conn.close()
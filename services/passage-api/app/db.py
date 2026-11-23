import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager

import pymssql

logger = logging.getLogger("passage-api.db")


def parse_connection_string(conn_str: str) -> dict:
    """Turn an ADO.NET-style string (what Azure Portal gives you) into pymssql kwargs.

    e.g. "Server=tcp:x.database.windows.net,1433;Initial Catalog=passage;
          User ID=app;Password=...;Encrypt=True;"
    """
    parts = {}
    for item in conn_str.split(";"):
        if "=" in item:
            key, value = item.split("=", 1)
            parts[key.strip().lower()] = value.strip()

    server = parts.get("server", parts.get("data source", "localhost"))
    server = server.removeprefix("tcp:")
    host, _, port = server.partition(",")
    return {
        "server": host,
        "port": int(port) if port else 1433,
        "database": parts.get("initial catalog", parts.get("database", "")),
        "user": parts.get("user id", parts.get("uid", "")),
        "password": parts.get("password", parts.get("pwd", "")),
    }


def connect(conn_str: str, database: str | None = None, autocommit: bool = False):
    kwargs = parse_connection_string(conn_str)
    if database is not None:
        kwargs["database"] = database
    return pymssql.connect(**kwargs, autocommit=autocommit, login_timeout=60, timeout=30)


def connect_with_retry(conn_str: str, attempts: int = 6, first_delay_s: float = 2.0, **kw):
    """Serverless SQL auto-pauses and the compose container starts slowly: back off and retry."""
    delay = first_delay_s
    for attempt in range(1, attempts + 1):
        try:
            return connect(conn_str, **kw)
        except pymssql.Error as exc:
            if attempt == attempts:
                raise
            logger.warning(
                "DB connect attempt %d/%d failed (%s); retrying in %.0fs",
                attempt,
                attempts,
                exc.__class__.__name__,
                delay,
            )
            time.sleep(delay)
            delay *= 2


@contextmanager
def get_connection(conn_str: str) -> Iterator:
    conn = connect_with_retry(conn_str, attempts=3)
    try:
        yield conn
    finally:
        conn.close()
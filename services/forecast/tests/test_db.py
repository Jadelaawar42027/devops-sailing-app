import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError

from app import db
from app.config import Settings, database_url_from_env


def test_migrations_create_tables(client):
    tables = set(inspect(client.app.state.engine).get_table_names())
    assert {"forecast_cache", "alembic_version"} <= tables


def test_migrations_are_idempotent(client):
    db.run_migrations(client.app.state.engine)  # second run is a no-op


def test_prepare_database_retries_then_raises(monkeypatch):
    calls = []

    def boom(engine):
        calls.append(1)
        raise OperationalError("SELECT 1", {}, Exception("paused"))

    monkeypatch.setattr(db, "run_migrations", boom)
    settings = Settings(db_connect_retries=3, db_retry_delay_s=0)
    with pytest.raises(OperationalError):
        db.prepare_database(settings, engine=None)
    assert len(calls) == 3


def test_database_error_returns_503_not_500(client, monkeypatch):
    def broken(*args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("database paused"))

    monkeypatch.setattr("sqlalchemy.orm.Session.scalar", broken)
    response = client.get("/forecast", params={"lat": 1, "lon": 1})
    assert response.status_code == 503
    assert "Database unavailable" in response.json()["detail"]


def test_database_url_from_env(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DB_HOST", raising=False)
    assert str(database_url_from_env()).startswith("sqlite")

    monkeypatch.setenv("DB_HOST", "sql.example.net")
    monkeypatch.setenv("DB_NAME", "fcdb")
    monkeypatch.setenv("DB_USER", "u")
    monkeypatch.setenv("DB_PASSWORD", "p@ss;word")
    url = database_url_from_env()
    assert url.drivername == "mssql+pyodbc"
    assert url.database == "fcdb"
    assert url.password == "p@ss;word"
    assert url.query["TrustServerCertificate"] == "no"

    monkeypatch.setenv("DATABASE_URL", "sqlite:///x.db")
    assert database_url_from_env() == "sqlite:///x.db"


def test_create_database_if_missing_ignores_sqlite():
    db.create_database_if_missing("sqlite:///:memory:")  # no-op, must not raise

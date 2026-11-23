"""DB code tested with fake pymssql connections: CI never touches a real database."""

from pathlib import Path

import pymssql
import pytest

from app import db, migrations


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql, params=None):
        self.conn.executed.append(sql)
        if self.conn.fail_on and self.conn.fail_on in sql:
            raise RuntimeError("boom")

    def fetchall(self):
        return [(v,) for v in self.conn.applied]


class FakeConn:
    def __init__(self, applied=(), fail_on=None):
        self.applied = list(applied)
        self.fail_on = fail_on
        self.executed, self.commits, self.rollbacks, self.closed = [], 0, 0, False

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


CS = "Server=sqlserver,1433;Database=passage;User ID=sa;Password=x"


@pytest.fixture
def migrations_dir(tmp_path: Path, monkeypatch):
    (tmp_path / "001_a.sql").write_text("CREATE TABLE a (id INT)")
    (tmp_path / "002_b.sql").write_text("CREATE TABLE b (id INT)")
    monkeypatch.setattr(migrations, "MIGRATIONS_DIR", tmp_path)
    monkeypatch.setattr(migrations.discover, "__defaults__", (tmp_path,))
    return tmp_path


def test_connect_passes_parsed_kwargs(monkeypatch):
    seen = {}
    monkeypatch.setattr(pymssql, "connect", lambda **kw: seen.update(kw) or "conn")
    assert db.connect(CS, database="master", autocommit=True) == "conn"
    assert seen["server"] == "sqlserver" and seen["database"] == "master"
    assert seen["autocommit"] is True


def test_retry_succeeds_after_failures(monkeypatch):
    calls = {"n": 0}

    def flaky(*_, **__):
        calls["n"] += 1
        if calls["n"] < 3:
            raise pymssql.OperationalError("paused")
        return "conn"

    monkeypatch.setattr(db, "connect", flaky)
    monkeypatch.setattr(db.time, "sleep", lambda _: None)
    assert db.connect_with_retry(CS) == "conn"
    assert calls["n"] == 3


def test_retry_gives_up(monkeypatch):
    def always_fail(*_, **__):
        raise pymssql.OperationalError("down")

    monkeypatch.setattr(db, "connect", always_fail)
    monkeypatch.setattr(db.time, "sleep", lambda _: None)
    with pytest.raises(pymssql.OperationalError):
        db.connect_with_retry(CS, attempts=2)


def test_get_connection_closes(monkeypatch):
    conn = FakeConn()
    monkeypatch.setattr(db, "connect_with_retry", lambda *_, **__: conn)
    with db.get_connection(CS) as c:
        assert c is conn
    assert conn.closed


def test_fresh_db_applies_all(monkeypatch, migrations_dir):
    conn = FakeConn(applied=[])
    monkeypatch.setattr(migrations, "connect_with_retry", lambda *_, **__: conn)
    assert migrations.run_migrations(CS) == [1, 2]
    assert conn.commits == 3  # schema_version table + one per file
    assert conn.closed


def test_existing_db_applies_only_new(monkeypatch, migrations_dir):
    conn = FakeConn(applied=[1])
    monkeypatch.setattr(migrations, "connect_with_retry", lambda *_, **__: conn)
    assert migrations.run_migrations(CS) == [2]


def test_up_to_date_db_is_noop(monkeypatch, migrations_dir):
    conn = FakeConn(applied=[1, 2])
    monkeypatch.setattr(migrations, "connect_with_retry", lambda *_, **__: conn)
    assert migrations.run_migrations(CS) == []


def test_failed_migration_rolls_back(monkeypatch, migrations_dir):
    conn = FakeConn(applied=[1], fail_on="TABLE b")
    monkeypatch.setattr(migrations, "connect_with_retry", lambda *_, **__: conn)
    with pytest.raises(RuntimeError):
        migrations.run_migrations(CS)
    assert conn.rollbacks == 1
    assert conn.closed


def test_create_db_if_missing(monkeypatch, migrations_dir):
    conns = []

    def fake_connect(*_, **__):
        conns.append(FakeConn())
        return conns[-1]

    monkeypatch.setattr(migrations, "connect_with_retry", fake_connect)
    migrations.run_migrations(CS, create_db=True)
    assert "CREATE DATABASE [passage]" in conns[0].executed[0]


def test_unsafe_db_name_rejected():
    with pytest.raises(ValueError):
        migrations.ensure_database("Server=s;Database=x];DROP--;User ID=a;Password=b")
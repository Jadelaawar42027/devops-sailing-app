from pathlib import Path

import pytest

from app.db import parse_connection_string
from app.migrations import discover, pending


def test_discover_sorts_by_version(tmp_path: Path):
    (tmp_path / "002_b.sql").write_text("SELECT 2")
    (tmp_path / "001_a.sql").write_text("SELECT 1")
    assert [v for v, _ in discover(tmp_path)] == [1, 2]


def test_discover_rejects_bad_names(tmp_path: Path):
    (tmp_path / "boats.sql").write_text("SELECT 1")
    with pytest.raises(ValueError):
        discover(tmp_path)


def test_discover_rejects_duplicate_versions(tmp_path: Path):
    (tmp_path / "001_a.sql").write_text("SELECT 1")
    (tmp_path / "001_b.sql").write_text("SELECT 1")
    with pytest.raises(ValueError):
        discover(tmp_path)


def test_pending_skips_applied(tmp_path: Path):
    for name in ("001_a.sql", "002_b.sql", "003_c.sql"):
        (tmp_path / name).write_text("SELECT 1")
    assert [v for v, _ in pending({1, 2}, discover(tmp_path))] == [3]


def test_real_migrations_folder_is_valid():
    assert discover()[0][0] == 1


def test_parse_azure_connection_string():
    cs = (
        "Server=tcp:demo.database.windows.net,1433;Initial Catalog=passage;"
        "User ID=app;Password=p@ss;Encrypt=True;"
    )
    assert parse_connection_string(cs) == {
        "server": "demo.database.windows.net",
        "port": 1433,
        "database": "passage",
        "user": "app",
        "password": "p@ss",
    }


def test_parse_local_connection_string_defaults_port():
    cs = "Server=sqlserver;Database=passage;User ID=sa;Password=x"
    assert parse_connection_string(cs)["port"] == 1433
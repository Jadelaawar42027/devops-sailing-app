import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings(tmp_path) -> Settings:
    # A real SQLite file so the Alembic migrations run exactly as on startup.
    return Settings(
        version="test",
        cors_origins=("http://ui.test",),
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        db_connect_retries=1,
    )


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c:
        yield c


BOAT = {"name": "Aurora", "max_wind_kn": 20, "max_gust_kn": 28, "max_wave_m": 2.0}


@pytest.fixture
def boat(client) -> dict:
    response = client.post("/boats", json=BOAT)
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def passage_body(boat) -> dict:
    return {
        "name": "Barcelona to Mallorca",
        "boat_id": boat["id"],
        "start_lat": 41.38,
        "start_lon": 2.18,
        "end_lat": 39.57,
        "end_lon": 2.65,
        "speed_kn": 6,
    }

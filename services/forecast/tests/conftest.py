import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

TIMES = ["2026-11-22T00:00", "2026-11-22T01:00", "2026-11-22T02:00"]
WEATHER = {
    "hourly": {
        "time": TIMES,
        "wind_speed_10m": [10.0, 12.5, 15.0],
        "wind_gusts_10m": [14.0, 18.0, 22.0],
        "wind_direction_10m": [270, 280, 290],
    },
    "current": {
        "time": "2026-11-22T01:15",
        "wind_speed_10m": 11.0,
        "wind_gusts_10m": 16.0,
        "wind_direction_10m": 275,
    },
}
MARINE = {
    "hourly": {
        "time": TIMES,
        "wave_height": [0.8, 1.1, None],
        "wave_direction": [250, 255, None],
        "wave_period": [5.0, 5.5, None],
    },
    "current": {
        "time": "2026-11-22T01:15",
        "wave_height": 0.9,
        "wave_direction": 252,
        "wave_period": 5.2,
    },
}


class FakeOpenMeteo:
    """Programmable stand-in for both Open-Meteo APIs."""

    def __init__(self) -> None:
        self.calls: list[httpx.Request] = []
        self.mode = "ok"  # ok | timeout | http500 | error_json | down

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        if self.mode == "timeout":
            raise httpx.ReadTimeout("timed out", request=request)
        if self.mode == "down":
            raise httpx.ConnectError("connection refused", request=request)
        if self.mode == "http500":
            return httpx.Response(500, json={"error": True})
        if self.mode == "error_json":
            return httpx.Response(200, json={"error": True, "reason": "Latitude out of range"})
        body = MARINE if "marine" in request.url.host else WEATHER
        return httpx.Response(200, json=body)


@pytest.fixture
def upstream() -> FakeOpenMeteo:
    return FakeOpenMeteo()


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        version="test",
        cors_origins=("http://ui.test",),
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        db_connect_retries=1,
    )


@pytest.fixture
def client(settings, upstream):
    http = httpx.Client(transport=httpx.MockTransport(upstream))
    with TestClient(create_app(settings, http=http)) as c:
        yield c

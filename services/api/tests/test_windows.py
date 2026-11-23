"""GET /passages/{id}/windows end to end, with the forecast service faked."""

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app

FRONT = json.loads((Path(__file__).parent / "fixtures" / "forecast_front_passing.json").read_text())


class FakeForecastService:
    def __init__(self) -> None:
        self.mode = "ok"  # ok | down | timeout | unavailable | stale | garbage
        self.calls: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        if self.mode == "down":
            raise httpx.ConnectError("connection refused", request=request)
        if self.mode == "timeout":
            raise httpx.ReadTimeout("timed out", request=request)
        if self.mode == "unavailable":
            detail = "Forecast unavailable: open-meteo-marine did not answer within 4s"
            return httpx.Response(503, json={"detail": detail})
        if self.mode == "garbage":
            return httpx.Response(200, json={"nope": True})
        if self.mode == "plain500":
            return httpx.Response(500, text="oops")
        return httpx.Response(200, json={**FRONT, "stale": self.mode == "stale"})


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch):
    # The fixture forecast starts 2026-11-23 00:00Z; pretend it is 00:20Z that day.
    monkeypatch.setattr(
        "app.routers.windows.utcnow", lambda: datetime(2026, 11, 23, 0, 20, tzinfo=UTC)
    )


@pytest.fixture
def forecast():
    return FakeForecastService()


@pytest.fixture
def client(settings, forecast):
    http = httpx.Client(transport=httpx.MockTransport(forecast))
    with TestClient(create_app(settings, http=http)) as c:
        yield c


@pytest.fixture
def passage(client, passage_body):
    # ~18.5 h passage at 6 kn: longer than our 24 h fixture allows for most departures.
    short = {**passage_body, "end_lat": 41.0, "end_lon": 2.18, "speed_kn": 6}  # ~22.8 nm
    return client.post("/passages", json=short).json()


def test_windows_are_scored(client, passage, forecast):
    response = client.get(f"/passages/{passage['id']}/windows")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["forecast"] == {
        "source": "open-meteo",
        "points": 2,
        "horizon_hours": 24,
        "stale": False,
    }
    assert body["duration_h"] == pytest.approx(3.8, abs=0.1)
    assert body["summary"]["windows"] == 20
    assert body["summary"]["go"] + body["summary"]["no_go"] == 20
    assert body["summary"]["first_go"].startswith("2026-11-23T00:00")
    nogo = next(w for w in body["windows"] if not w["go"])
    assert nogo["failures"][0]["exceeded_by"] > 0
    assert "exceeds limit" in nogo["reason"]
    # One forecast call per point, with the configured horizon.
    assert len(forecast.calls) == 2
    assert forecast.calls[0].url.params["days"] == "3"


def test_same_start_and_end_fetches_one_point(client, passage_body, forecast):
    body = {
        **passage_body,
        "end_lat": passage_body["start_lat"],
        "end_lon": passage_body["start_lon"],
    }
    pid = client.post("/passages", json=body).json()["id"]
    response = client.get(f"/passages/{pid}/windows")
    assert response.json()["forecast"]["points"] == 1
    assert len(forecast.calls) == 1


def test_long_passage_explains_empty_result(client, passage_body):
    far = {**passage_body, "end_lat": 30.0, "speed_kn": 2}
    pid = client.post("/passages", json=far).json()["id"]
    body = client.get(f"/passages/{pid}/windows").json()
    assert body["windows"] == []
    assert body["summary"]["note"] == "Passage is longer than the forecast horizon."


def test_stale_forecast_is_flagged(client, passage, forecast):
    forecast.mode = "stale"
    assert client.get(f"/passages/{passage['id']}/windows").json()["forecast"]["stale"] is True


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("down", "forecast service is unreachable"),
        ("timeout", "did not answer within 10s"),
        ("unavailable", "open-meteo-marine did not answer within 4s"),
        ("garbage", "unexpected response"),
        ("plain500", "answered HTTP 500"),
    ],
)
def test_forecast_failure_gives_clear_degraded_response(client, passage, forecast, mode, expected):
    forecast.mode = mode
    response = client.get(f"/passages/{passage['id']}/windows")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert expected in body["detail"]
    assert "Boats and passages still work" in body["detail"]
    assert body["windows"] == []


def test_crud_keeps_working_while_forecast_is_down(client, passage, forecast):
    forecast.mode = "down"
    assert client.get("/boats").status_code == 200
    assert client.get(f"/passages/{passage['id']}").status_code == 200
    created = client.post("/boats", json={"name": "Spare", "max_wind_kn": 18, "max_wave_m": 1.5})
    assert created.status_code == 201


def test_past_departures_are_not_listed(client, passage, monkeypatch):
    monkeypatch.setattr(
        "app.routers.windows.utcnow", lambda: datetime(2026, 11, 23, 10, 5, tzinfo=UTC)
    )
    body = client.get(f"/passages/{passage['id']}/windows").json()
    assert body["windows"][0]["departure"].startswith("2026-11-23T10:00")
    assert body["summary"]["windows"] == 10


def test_windows_for_missing_passage_is_404(client):
    assert client.get("/passages/999/windows").status_code == 404

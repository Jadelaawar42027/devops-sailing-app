import dataclasses
import logging

import httpx
from fastapi.testclient import TestClient

from app import cache
from app.main import create_app
from app.openmeteo import merge_hourly


def test_forecast_merges_wind_and_waves(client):
    response = client.get("/forecast", params={"lat": 41.38, "lon": 2.18})
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "open-meteo"
    assert body["cache"] == "miss"
    assert body["stale"] is False
    assert len(body["hours"]) == 3
    first = body["hours"][0]
    assert first == {
        "time": "2026-11-22T00:00Z",
        "wind_kn": 10.0,
        "gust_kn": 14.0,
        "wind_dir_deg": 270,
        "wave_m": 0.8,
        "wave_dir_deg": 250,
        "wave_period_s": 5.0,
    }
    assert body["hours"][2]["wave_m"] is None  # missing upstream value stays None


def test_forecast_requests_knots_utc_and_days(client, upstream):
    client.get("/forecast", params={"lat": 41.38, "lon": 2.18, "days": 2})
    weather = next(r for r in upstream.calls if "marine" not in r.url.host)
    assert weather.url.params["wind_speed_unit"] == "kn"
    assert weather.url.params["timezone"] == "UTC"
    assert weather.url.params["forecast_days"] == "2"


def test_second_call_is_served_from_cache(client, upstream):
    client.get("/forecast", params={"lat": 41.38, "lon": 2.18})
    calls = len(upstream.calls)
    response = client.get("/forecast", params={"lat": 41.381, "lon": 2.182})  # same 2-dp cell
    assert response.json()["cache"] == "hit"
    assert len(upstream.calls) == calls


def test_upstream_timeout_without_cache_is_a_clear_503(client, upstream):
    upstream.mode = "timeout"
    response = client.get("/forecast", params={"lat": 41.38, "lon": 2.18})
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "did not answer within 4s" in detail
    assert "no cached data" in detail


def test_upstream_http_error_is_a_clear_503(client, upstream):
    upstream.mode = "http500"
    response = client.get("/current", params={"lat": 41.38, "lon": 2.18})
    assert response.status_code == 503
    assert "answered HTTP 500" in response.json()["detail"]


def test_upstream_error_payload_is_a_clear_503(client, upstream):
    upstream.mode = "error_json"
    response = client.get("/forecast", params={"lat": 41.38, "lon": 2.18})
    assert response.status_code == 503
    assert "Latitude out of range" in response.json()["detail"]


def test_upstream_unreachable_is_a_clear_503(client, upstream):
    upstream.mode = "down"
    response = client.get("/forecast", params={"lat": 41.38, "lon": 2.18})
    assert response.status_code == 503
    assert "unreachable" in response.json()["detail"]


def test_stale_cache_is_served_when_upstream_fails(settings, upstream):
    expired = dataclasses.replace(settings, forecast_ttl_s=0)
    http = httpx.Client(transport=httpx.MockTransport(upstream))
    with TestClient(create_app(expired, http=http)) as client:
        assert client.get("/forecast", params={"lat": 41.38, "lon": 2.18}).status_code == 200
        upstream.mode = "timeout"
        response = client.get("/forecast", params={"lat": 41.38, "lon": 2.18})
    assert response.status_code == 200
    assert response.json()["cache"] == "stale"
    assert response.json()["stale"] is True
    assert len(response.json()["hours"]) == 3


def test_current_conditions(client):
    response = client.get("/current", params={"lat": 41.38, "lon": 2.18})
    assert response.status_code == 200
    assert response.json()["current"] == {
        "time": "2026-11-22T01:15Z",
        "wind_kn": 11.0,
        "gust_kn": 16.0,
        "wind_dir_deg": 275,
        "wave_m": 0.9,
        "wave_dir_deg": 252,
        "wave_period_s": 5.2,
    }


def test_invalid_coordinates_are_rejected(client):
    assert client.get("/forecast", params={"lat": 91, "lon": 0}).status_code == 422
    assert client.get("/forecast", params={"lat": 0, "lon": 181}).status_code == 422
    assert client.get("/forecast", params={"lat": 0, "lon": 0, "days": 8}).status_code == 422
    assert client.get("/current", params={"lat": 0}).status_code == 422


def test_upstream_calls_are_logged(client, caplog):
    with caplog.at_level(logging.INFO, logger="upstream"):
        client.get("/current", params={"lat": 41.38, "lon": 2.18})
    names = [r.fields["upstream"] for r in caplog.records if r.name == "upstream"]
    assert names == ["open-meteo-weather", "open-meteo-marine"]


def test_merge_handles_missing_series():
    hours = merge_hourly({"time": ["2026-11-22T00:00"], "wind_speed_10m": [5.0]}, {})
    assert hours == [
        {
            "time": "2026-11-22T00:00Z",
            "wind_kn": 5.0,
            "gust_kn": None,
            "wind_dir_deg": None,
            "wave_m": None,
            "wave_dir_deg": None,
            "wave_period_s": None,
        }
    ]


def test_cache_key_rounds_and_includes_days():
    assert cache.cache_key("forecast", 41.3812, 2.1789, 3) == "forecast:41.38:2.18:3"
    assert cache.cache_key("current", -1.0, 0.0) == "current:-1.00:0.00"


def test_cache_put_overwrites(client):
    with client.app.state.session_factory() as session:
        cache.put(session, "k", {"data": 1})
        cache.put(session, "k", {"data": 2})
        payload, age = cache.get(session, "k")
    assert payload == {"data": 2}
    assert age >= 0

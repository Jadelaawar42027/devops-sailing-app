import json
import logging

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_request_is_logged_as_one_json_line(caplog):
    with caplog.at_level(logging.INFO, logger="passage-api.requests"):
        client.get("/health")
    lines = [r.getMessage() for r in caplog.records if r.name == "passage-api.requests"]
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["method"] == "GET"
    assert entry["path"] == "/health"
    assert entry["status"] == 200
    assert entry["duration_ms"] >= 0


def test_unknown_route_uses_error_shape():
    response = client.get("/nope")
    assert response.status_code == 404
    assert response.json() == {"error": "Not Found", "code": "NOT_FOUND"}


def test_cors_allows_only_configured_origin():
    ok = client.get("/health", headers={"Origin": "http://localhost:8080"})
    bad = client.get("/health", headers={"Origin": "https://evil.example"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:8080"
    assert "access-control-allow-origin" not in bad.headers


def test_api_error_uses_error_shape():
    from app.errors import ApiError

    @app.get("/_test_conflict")
    def conflict():
        raise ApiError(409, "BOAT_HAS_PASSAGES", "Boat has passages")

    response = client.get("/_test_conflict")
    assert response.status_code == 409
    assert response.json() == {"error": "Boat has passages", "code": "BOAT_HAS_PASSAGES"}
import json
import logging


def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "api", "version": "test"}


def test_one_structured_log_line_per_request(client, caplog):
    with caplog.at_level(logging.INFO, logger="request"):
        client.get("/health")
    records = [r for r in caplog.records if r.name == "request"]
    assert len(records) == 1
    fields = records[0].fields
    assert fields["method"] == "GET"
    assert fields["route"] == "/health"
    assert fields["status"] == 200
    assert fields["duration_ms"] >= 0


def test_json_formatter_outputs_parseable_line():
    from app.logging_setup import JsonFormatter

    record = logging.LogRecord("request", logging.INFO, __file__, 1, "request", None, None)
    record.fields = {"status": 200}
    line = json.loads(JsonFormatter("api").format(record))
    assert line["service"] == "api"
    assert line["status"] == 200
    assert line["level"] == "INFO"


def test_cors_allows_only_ui_origin(client):
    ok = client.options(
        "/health",
        headers={"Origin": "http://ui.test", "Access-Control-Request-Method": "GET"},
    )
    assert ok.headers.get("access-control-allow-origin") == "http://ui.test"
    bad = client.options(
        "/health",
        headers={"Origin": "http://evil.test", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in bad.headers

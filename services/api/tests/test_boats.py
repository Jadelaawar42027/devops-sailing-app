import pytest

from tests.conftest import BOAT


def test_create_and_get_boat(client, boat):
    assert boat["id"] > 0
    assert boat["name"] == "Aurora"
    assert client.get(f"/boats/{boat['id']}").json()["max_wave_m"] == 2.0


def test_list_boats(client, boat):
    response = client.get("/boats")
    assert response.status_code == 200
    assert [b["id"] for b in response.json()] == [boat["id"]]


def test_update_boat(client, boat):
    body = {**BOAT, "name": "Aurora II", "max_wind_kn": 22}
    response = client.put(f"/boats/{boat['id']}", json=body)
    assert response.status_code == 200
    assert response.json()["name"] == "Aurora II"
    assert response.json()["max_wind_kn"] == 22


def test_delete_boat(client, boat):
    assert client.delete(f"/boats/{boat['id']}").status_code == 204
    assert client.get(f"/boats/{boat['id']}").status_code == 404


def test_missing_boat_returns_404(client):
    assert client.get("/boats/999").status_code == 404
    assert client.put("/boats/999", json=BOAT).status_code == 404
    assert client.delete("/boats/999").status_code == 404


def test_name_is_trimmed_and_gust_optional(client):
    response = client.post("/boats", json={**BOAT, "name": "  Breeze  ", "max_gust_kn": None})
    assert response.status_code == 201
    assert response.json()["name"] == "Breeze"
    assert response.json()["max_gust_kn"] is None


@pytest.mark.parametrize(
    "change",
    [
        {"name": ""},
        {"name": "x" * 101},
        {"max_wind_kn": 0},
        {"max_wind_kn": -5},
        {"max_wave_m": 0},
        {"max_wave_m": 99},
        {"max_gust_kn": 10},  # below max_wind_kn
        {"unknown": 1},
    ],
)
def test_invalid_boat_is_rejected(client, change):
    response = client.post("/boats", json={**BOAT, **change})
    assert response.status_code == 422


def test_cannot_delete_boat_with_passages(client, boat, passage_body):
    assert client.post("/passages", json=passage_body).status_code == 201
    response = client.delete(f"/boats/{boat['id']}")
    assert response.status_code == 409
    assert "passages" in response.json()["detail"]

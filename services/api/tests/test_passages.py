import pytest


def test_passage_crud_roundtrip(client, passage_body):
    created = client.post("/passages", json=passage_body)
    assert created.status_code == 201
    pid = created.json()["id"]

    assert client.get(f"/passages/{pid}").json()["name"] == "Barcelona to Mallorca"

    updated = client.put(f"/passages/{pid}", json={**passage_body, "speed_kn": 7.5})
    assert updated.status_code == 200
    assert updated.json()["speed_kn"] == 7.5

    assert client.delete(f"/passages/{pid}").status_code == 204
    assert client.get(f"/passages/{pid}").status_code == 404


def test_list_passages_filters_by_boat(client, passage_body):
    client.post("/passages", json=passage_body)
    other = client.post("/boats", json={"name": "Other", "max_wind_kn": 15, "max_wave_m": 1}).json()
    client.post("/passages", json={**passage_body, "boat_id": other["id"], "name": "Other trip"})

    assert len(client.get("/passages").json()) == 2
    only = client.get(f"/passages?boat_id={other['id']}").json()
    assert [p["name"] for p in only] == ["Other trip"]


def test_passage_for_unknown_boat_is_rejected(client, passage_body):
    response = client.post("/passages", json={**passage_body, "boat_id": 999})
    assert response.status_code == 422
    assert response.json()["detail"] == "Boat 999 does not exist"


def test_missing_passage_returns_404(client, passage_body):
    assert client.get("/passages/999").status_code == 404
    assert client.put("/passages/999", json=passage_body).status_code == 404
    assert client.delete("/passages/999").status_code == 404


@pytest.mark.parametrize(
    "change",
    [
        {"start_lat": 91},
        {"end_lat": -91},
        {"start_lon": 181},
        {"end_lon": -181},
        {"speed_kn": 0},
        {"speed_kn": 41},
        {"name": ""},
        {"boat_id": 0},
    ],
)
def test_invalid_passage_is_rejected(client, passage_body, change):
    assert client.post("/passages", json={**passage_body, **change}).status_code == 422

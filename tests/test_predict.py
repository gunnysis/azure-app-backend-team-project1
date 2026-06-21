from tests.conftest import API_HEADERS


async def test_predict_ok(client):
    r = await client.post(
        "/api/v1/predict", json={"inputs": [1.0, 2.0, 3.0]}, headers=API_HEADERS
    )
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["predictions"], list)
    assert body["model_version"] == "mock-1.0"
    assert "elapsed_ms" in body


async def test_predict_deterministic(client):
    payload = {"inputs": [1.0, 2.0]}
    r1 = await client.post("/api/v1/predict", json=payload, headers=API_HEADERS)
    r2 = await client.post("/api/v1/predict", json=payload, headers=API_HEADERS)
    assert r1.json()["predictions"] == r2.json()["predictions"]


async def test_predict_dict_inputs(client):
    r = await client.post(
        "/api/v1/predict", json={"inputs": {"a": 1.0}}, headers=API_HEADERS
    )
    assert r.status_code == 200


async def test_extra_field_rejected(client):
    r = await client.post(
        "/api/v1/predict",
        json={"inputs": [1.0], "unexpected": 1},
        headers=API_HEADERS,
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_missing_inputs_rejected(client):
    r = await client.post("/api/v1/predict", json={}, headers=API_HEADERS)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"

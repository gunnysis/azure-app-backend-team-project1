async def test_missing_api_key(client):
    r = await client.post("/api/v1/predict", json={"inputs": [1.0, 2.0]})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "AUTH_INVALID"


async def test_wrong_api_key(client):
    r = await client.post(
        "/api/v1/predict",
        json={"inputs": [1.0]},
        headers={"X-API-Key": "wrong"},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "AUTH_INVALID"

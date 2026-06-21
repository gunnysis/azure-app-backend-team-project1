async def test_liveness(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_readiness(client):
    r = await client.get("/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["ml"] is True


async def test_request_id_header_present(client):
    r = await client.get("/health")
    assert "X-Request-ID" in r.headers


async def test_request_id_inherited(client):
    r = await client.get("/health", headers={"X-Request-ID": "abc123"})
    assert r.headers["X-Request-ID"] == "abc123"

from tests.conftest import API_HEADERS

# 검증된 계약(test4 swagger)의 입력 1행.
SAMPLE_ROW = {
    "prev_year_usage": 76,
    "avg_temp": -0.46,
    "avg_humidity": 66.55,
    "total_rainfall": 21.1,
    "current_usage": 53,
    "thi": 36.1076813,
    "month_sin": 0.5,
    "month_cos": 0.8660254037844387,
}


async def test_predict_ok(client):
    r = await client.post(
        "/api/v1/predict", json={"inputs": [SAMPLE_ROW]}, headers=API_HEADERS
    )
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["predictions"], list)
    assert body["model_version"] == "mock-1.0"
    assert "elapsed_ms" in body


async def test_predict_deterministic(client):
    payload = {"inputs": [SAMPLE_ROW]}
    r1 = await client.post("/api/v1/predict", json=payload, headers=API_HEADERS)
    r2 = await client.post("/api/v1/predict", json=payload, headers=API_HEADERS)
    assert r1.json()["predictions"] == r2.json()["predictions"]


async def test_predict_one_prediction_per_row(client):
    # 실제 엔드포인트처럼 입력 행 수만큼 예측이 나와야 한다.
    payload = {"inputs": [SAMPLE_ROW, {**SAMPLE_ROW, "current_usage": 129}]}
    r = await client.post("/api/v1/predict", json=payload, headers=API_HEADERS)
    assert r.status_code == 200
    assert len(r.json()["predictions"]) == 2


async def test_extra_field_rejected(client):
    r = await client.post(
        "/api/v1/predict",
        json={"inputs": [SAMPLE_ROW], "unexpected": 1},
        headers=API_HEADERS,
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_missing_inputs_rejected(client):
    r = await client.post("/api/v1/predict", json={}, headers=API_HEADERS)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_empty_inputs_rejected(client):
    # inputs 는 1건 이상이어야 한다(min_length=1).
    r = await client.post(
        "/api/v1/predict", json={"inputs": []}, headers=API_HEADERS
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_non_dict_row_rejected(client):
    # 행은 객체여야 한다 — 예전 list[float] 형식은 이제 거부.
    r = await client.post(
        "/api/v1/predict", json={"inputs": [1.0, 2.0, 3.0]}, headers=API_HEADERS
    )
    assert r.status_code == 422

from tests.conftest import API_HEADERS, SAMPLE_ROW  # 샘플은 스키마 단일 진실원에서


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


def test_swagger_example_is_a_valid_request():
    # 재발방지: Swagger /docs 에 노출되는 예시가 단일 진실원에서 파생되고,
    # 그 자체로 유효한 PredictRequest 여야 한다(예시-스키마 드리프트 차단).
    from app.schemas.prediction import EXAMPLE_INPUT_ROW, PredictRequest

    example = PredictRequest.model_json_schema()["example"]
    assert example == {"inputs": [EXAMPLE_INPUT_ROW]}
    PredictRequest.model_validate(example)  # raise 없이 통과해야 함


async def test_predict_accepts_swagger_example(client):
    # 문서화된 예시 페이로드가 실제 엔드포인트에서 200 이어야 한다(계약 일관성).
    from app.schemas.prediction import PredictRequest

    example = PredictRequest.model_json_schema()["example"]
    r = await client.post("/api/v1/predict", json=example, headers=API_HEADERS)
    assert r.status_code == 200
    assert isinstance(r.json()["predictions"], list)

"""AzureMLClient 단위 테스트 — 실제 엔드포인트 호출 없이 httpx.MockTransport 로 검증.

라이브 호출/과금 없음. Settings 는 _env_file=None 으로 실제 .env 와 격리한다
(실 시크릿 로드·노출 방지). 재시도 대기는 asyncio.sleep 패치로 즉시 진행한다.
"""

import json

import httpx
import pytest

from app.config import Settings
from app.core.errors import MLTimeoutError, MLUnavailableError, UpstreamError
from app.ml.azure import AzureMLClient
from app.schemas.prediction import EXAMPLE_INPUT_ROW as SAMPLE_ROW  # 단일 진실원 재사용
from app.schemas.prediction import PredictRequest

REQ = PredictRequest(inputs=[SAMPLE_ROW])


def _make_client(handler, *, max_retries: int = 2) -> AzureMLClient:
    settings = Settings(
        _env_file=None,  # 실 .env 격리 — 시크릿 로드 방지
        azure_ml_scoring_uri="http://test.local/score",
        azure_ml_auth_pri_key="PRI",
        ml_max_retries=max_retries,
    )
    client = AzureMLClient(settings)
    # 테스트 seam: 실제 네트워크 대신 MockTransport 주입(Bearer 헤더 유지).
    client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        headers={"Authorization": "Bearer PRI", "Content-Type": "application/json"},
    )
    return client


@pytest.fixture
def no_sleep(monkeypatch):
    async def _instant(_seconds):
        return None

    monkeypatch.setattr("app.ml.azure.asyncio.sleep", _instant)


# --- 순수 변환 함수 ---------------------------------------------------------

def test_to_payload_wraps_designer_envelope():
    payload = AzureMLClient._to_aml_payload(REQ)
    assert payload == {"Inputs": {"input1": [SAMPLE_ROW]}, "GlobalParameters": {}}


def test_from_response_extracts_scored_labels_to_match_mock_shape():
    # 'Scored Labels' 점수만 추출 → Mock 과 동일한 list[점수] 형태.
    assert AzureMLClient._from_aml_response(
        {"Results": {"WebServiceOutput0": [{"prev_year_usage": 76, "Scored Labels": 1.2}]}}
    ) == [1.2]
    # 여러 행 → 행 수만큼 점수.
    assert AzureMLClient._from_aml_response(
        {"Results": {"WebServiceOutput0": [{"Scored Labels": 1}, {"Scored Labels": 2}]}}
    ) == [1, 2]
    # 출력 포트명이 달라도 Results 의 첫 배열을 취한다(모델 교체 내성).
    assert AzureMLClient._from_aml_response({"Results": {"OtherPort": [9]}}) == [9]
    # 'Scored Labels' 가 없으면 행 전체 보존(스키마 교체 내성).
    assert AzureMLClient._from_aml_response(
        {"Results": {"WebServiceOutput0": [{"a": 1}]}}
    ) == [{"a": 1}]
    # 폴백: 배열 그대로 / 스칼라는 단일 원소 리스트.
    assert AzureMLClient._from_aml_response([1, 2]) == [1, 2]
    assert AzureMLClient._from_aml_response("x") == ["x"]


# --- 생성/검증 -------------------------------------------------------------

def test_missing_key_or_uri_raises_valueerror():
    with pytest.raises(ValueError):  # 키 없음
        AzureMLClient(Settings(_env_file=None, azure_ml_scoring_uri="http://x/score"))
    with pytest.raises(ValueError):  # URI 없음
        AzureMLClient(Settings(_env_file=None, azure_ml_auth_pri_key="K"))


def test_secondary_key_used_when_primary_absent():
    settings = Settings(
        _env_file=None,
        azure_ml_scoring_uri="http://x/score",
        azure_ml_auth_sec_key="SEC",
    )
    client = AzureMLClient(settings)
    assert client._client.headers["Authorization"] == "Bearer SEC"


# --- predict() 흐름 (MockTransport) ----------------------------------------

async def test_predict_happy_path_sends_envelope_and_parses():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        seen["auth"] = request.headers.get("Authorization")
        return httpx.Response(
            200,
            json={"Results": {"WebServiceOutput0": [{**SAMPLE_ROW, "Scored Labels": 61.2}]}},
            headers={"azureml-model-version": "v7"},
        )

    client = _make_client(handler)
    resp = await client.predict(REQ)
    await client.aclose()

    assert seen["body"] == {"Inputs": {"input1": [SAMPLE_ROW]}, "GlobalParameters": {}}
    assert seen["auth"] == "Bearer PRI"
    assert resp.predictions == [61.2]  # 'Scored Labels' 추출 (Mock 과 동일 형태)
    assert resp.model_version == "v7"
    assert resp.elapsed_ms >= 0


async def test_4xx_raises_upstream_without_retry():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(400, json={"message": "bad input"})

    client = _make_client(handler, max_retries=2)
    with pytest.raises(UpstreamError):
        await client.predict(REQ)
    await client.aclose()
    assert calls["n"] == 1  # 4xx 는 재시도하지 않음


async def test_5xx_retries_then_unavailable(no_sleep):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503)

    client = _make_client(handler, max_retries=2)
    with pytest.raises(MLUnavailableError):
        await client.predict(REQ)
    await client.aclose()
    assert calls["n"] == 3  # 최초 1 + 재시도 2


async def test_5xx_then_success_recovers(no_sleep):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(500)
        return httpx.Response(200, json={"Results": {"WebServiceOutput0": [{"Scored Labels": 1.0}]}})

    client = _make_client(handler, max_retries=2)
    resp = await client.predict(REQ)
    await client.aclose()
    assert calls["n"] == 2
    assert resp.predictions == [1.0]


async def test_timeout_raises_ml_timeout(no_sleep):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    client = _make_client(handler, max_retries=1)
    with pytest.raises(MLTimeoutError):
        await client.predict(REQ)
    await client.aclose()

"""어댑터 엔드포인트(/api/v1/estimate) + 피처빌더 테스트."""

import asyncio
import math
import time

import pytest

from app.data.seoul_climate import monthly_weather
from app.config import get_settings
from app.main import app
from app.ml.base import MLClient
from app.schemas.prediction import EXAMPLE_INPUT_ROW, PredictRequest, PredictResponse
from app.services.feature_builder import (
    BASE_MONTHLY_KWH,
    build_features,
    compute_thi,
    estimate_usage,
)


class _SlowML(MLClient):
    """예산 초과를 유발하는 느린 스텁(타임아웃 강제 검증용)."""

    async def predict(self, request: PredictRequest) -> PredictResponse:
        await asyncio.sleep(5)
        return PredictResponse(predictions=[0.5, 0.4], model_version="slow", elapsed_ms=5000)

    async def health(self) -> bool:
        return True


class _SingleRowML(MLClient):
    """행을 1개만 반환하는 스텁(baseline 행 결측 시 graceful degrade 검증용)."""

    async def predict(self, request: PredictRequest) -> PredictResponse:
        return PredictResponse(predictions=[0.5], model_version="single", elapsed_ms=1.0)

    async def health(self) -> bool:
        return True

ESTIMATE = "/api/v1/estimate"
SAMPLE_INPUT = {
    "region": "mapo",
    "housing_type": "oneroom",
    "household_size": 1,
    "has_aircon": True,
    "aircon_hours_per_day": 6,
    "aircon_power_w": None,
    "aircon_type": "inverter",
    "month": 7,
}


# --- 엔드포인트 ---


async def test_estimate_ok_without_api_key(client):
    # 무키 엔드포인트 — X-API-Key 없이도 200.
    r = await client.post(ESTIMATE, json=SAMPLE_INPUT)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["predicted_kwh"], (int, float))
    assert body["month"] == 7
    assert body["model_version"] == "mock-1.0"
    assert set(body["features_used"]) == set(EXAMPLE_INPUT_ROW)


async def test_estimate_deterministic(client):
    r1 = await client.post(ESTIMATE, json=SAMPLE_INPUT)
    r2 = await client.post(ESTIMATE, json=SAMPLE_INPUT)
    assert r1.json()["predicted_kwh"] == r2.json()["predicted_kwh"]


async def test_estimate_defaults_month_when_omitted(client):
    payload = {k: v for k, v in SAMPLE_INPUT.items() if k != "month"}
    r = await client.post(ESTIMATE, json=payload)
    assert r.status_code == 200
    assert 1 <= r.json()["month"] <= 12  # 서버 현재 월로 채워짐.


async def test_estimate_extra_field_rejected(client):
    r = await client.post(ESTIMATE, json={**SAMPLE_INPUT, "unexpected": 1})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_estimate_hours_out_of_range_rejected(client):
    r = await client.post(ESTIMATE, json={**SAMPLE_INPUT, "aircon_hours_per_day": 25})
    assert r.status_code == 422


async def test_estimate_minimal_payload(client):
    # 필수는 aircon_hours_per_day 뿐(나머지 기본값). 미사용(0시간) 케이스.
    r = await client.post(ESTIMATE, json={"aircon_hours_per_day": 0, "month": 1})
    assert r.status_code == 200
    feats = r.json()["features_used"]
    # 0시간 → current_usage == 기저 사용량.
    assert feats["current_usage"] == pytest.approx(BASE_MONTHLY_KWH)


# --- baseline (계절성 기준선) ---


async def test_estimate_returns_baseline_kwh(client):
    # 백엔드가 동적 기준선을 함께 내려준다(프론트 고정 165 폴백 대체).
    r = await client.post(ESTIMATE, json=SAMPLE_INPUT)
    assert isinstance(r.json()["baseline_kwh"], (int, float))


async def test_estimate_baseline_equals_prediction_when_aircon_off(client):
    # 0시간 → 사용자 피처 == baseline 피처(둘 다 에어컨 OFF·동월) → 두 점수 동일해야 한다.
    r = await client.post(ESTIMATE, json={"aircon_hours_per_day": 0, "month": 7})
    body = r.json()
    assert body["baseline_kwh"] == body["predicted_kwh"]


async def test_estimate_baseline_differs_when_aircon_on(client):
    # 6시간 → 사용자 피처 ≠ baseline 피처 → 기준선이 무에어컨 기준을 반영(다른 값).
    body = (await client.post(ESTIMATE, json=SAMPLE_INPUT)).json()
    assert body["baseline_kwh"] != body["predicted_kwh"]


async def test_estimate_baseline_none_when_single_prediction(client):
    # 모델이 행 1개만 반환해도 깨지지 않고 baseline=None 으로 graceful degrade.
    app.state.ml_client = _SingleRowML()
    r = await client.post(ESTIMATE, json=SAMPLE_INPUT)
    body = r.json()
    assert r.status_code == 200
    assert body["baseline_kwh"] is None
    assert isinstance(body["predicted_kwh"], (int, float))


# --- 타임아웃 총 예산 강제 (① 근본 해결 회귀 방지) ---


async def test_estimate_timeout_returns_504_within_budget(client, monkeypatch):
    # 예산(0.1s)을 넘는 ML 호출은 재시도 낭비 없이 즉시 504 — 5s sleep을 끊었는지로 확인.
    monkeypatch.setattr(get_settings(), "estimate_ml_deadline_s", 0.1)
    app.state.ml_client = _SlowML()
    start = time.perf_counter()
    r = await client.post(ESTIMATE, json=SAMPLE_INPUT)
    elapsed = time.perf_counter() - start
    assert r.status_code == 504
    assert r.json()["error"]["code"] == "ML_TIMEOUT"
    assert elapsed < 2.0  # 5s 스텁이 예산에서 잘려 빠르게 반환(낭비 차단)


# --- 피처빌더 단위 ---


def test_thi_matches_operational_example():
    # 운영 모델 EXAMPLE_INPUT_ROW를 역산해 확인한 식과 일치해야 한다.
    thi = compute_thi(EXAMPLE_INPUT_ROW["avg_temperature"], EXAMPLE_INPUT_ROW["avg_humidity"])
    assert thi == pytest.approx(EXAMPLE_INPUT_ROW["thi"], abs=1e-6)


def test_month_trig_encoding():
    feats = build_features(
        month=1, aircon_hours_per_day=0, aircon_power_w=None, aircon_type="none"
    )
    # 1월 → 2π/12 = 30°, sin=0.5, cos=√3/2.
    assert feats["month_sin"] == pytest.approx(0.5, abs=1e-9)
    assert feats["month_cos"] == pytest.approx(math.sqrt(3) / 2, abs=1e-9)


def test_weather_lookup_wired_into_features():
    temp, hum, rain = monthly_weather(7)
    feats = build_features(
        month=7, aircon_hours_per_day=3, aircon_power_w=600, aircon_type="inverter"
    )
    assert feats["avg_temperature"] == temp
    assert feats["avg_humidity"] == hum
    assert feats["total_rainfall"] == rain


def test_usage_increases_with_hours():
    _, low = estimate_usage(2, None, "inverter")
    _, high = estimate_usage(10, None, "inverter")
    assert high > low
    # prev_year_usage는 기저 고정.
    prev, _ = estimate_usage(10, None, "inverter")
    assert prev == pytest.approx(BASE_MONTHLY_KWH)


def test_usage_clamped_to_model_range():
    # 비현실적으로 긴 가동도 학습 분포 상한으로 클램프.
    _, current = estimate_usage(24, 2000, "fixed")
    assert current <= 650.0


def test_build_features_has_all_eight_keys():
    feats = build_features(
        month=8, aircon_hours_per_day=5, aircon_power_w=None, aircon_type="fixed"
    )
    assert set(feats) == set(EXAMPLE_INPUT_ROW)
    assert all(isinstance(v, (int, float)) for v in feats.values())

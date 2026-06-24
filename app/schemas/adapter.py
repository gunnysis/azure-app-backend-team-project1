"""어댑터(사용자 의도 → 예측) 요청/응답 스키마.

프론트(찌릿)는 에어컨 습관만 수집한다. 이 스키마는 그 페이로드를 그대로 받아
백엔드가 8개 ML 피처로 변환(app/services/feature_builder.py)한 뒤 예측한다.
원시 `/api/v1/predict`(8피처·API Key 필수)와 달리, 이 엔드포인트는 정적 프론트가
호출하므로 무키(CORS 화이트리스트 + rate limit로 보호)다.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AirconType = Literal["fixed", "inverter", "unknown", "none"]


class EstimateRequest(BaseModel):
    # 프론트 buildPayload(script.js)와 1:1. 알 수 없는 필드는 422로 차단.
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "region": "mapo",
                "housing_type": "oneroom",
                "household_size": 1,
                "has_aircon": True,
                "aircon_hours_per_day": 6,
                "aircon_power_w": None,
                "aircon_type": "inverter",
            }
        },
    )

    # MVP는 마포·원룸·1인 고정이지만, 프론트가 보내는 값을 그대로 수용한다.
    region: str = "mapo"
    housing_type: str = "oneroom"
    household_size: int = Field(default=1, ge=1)
    has_aircon: bool = True
    aircon_hours_per_day: float = Field(ge=0, le=24)
    # number → 실측 전력, None → 타입 평균값 사용, 0 → 미사용.
    aircon_power_w: float | None = Field(default=None, ge=0)
    aircon_type: AirconType = "unknown"
    # 예측 대상 월(1~12). 생략 시 서버의 현재 월(KST)을 사용.
    #-----------------------------
    # month: int | None = Field(default=None, ge=1, le=12)
    # custom 8월 기준으로 예측
    month = 8

class EstimateResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    # 프론트 normalizePredictionResponse가 요구하는 필수 필드.
    predicted_kwh: float
    # 같은 ML 호출에 동봉한 '에어컨 OFF·동월·동일 기상' 예측 = 계절성 기준 사용량.
    # 프론트가 비교 기준으로 사용(없으면 프론트 기본값 165kWh로 폴백). 모델 응답이 행을
    # 1개만 주는 등 baseline 행이 비면 None → 프론트 폴백. 요금은 프론트가 kWh에서
    # 단일 요금식으로 계산(요금식 이중화·드리프트 방지 — 백엔드는 bill을 내려주지 않음).
    baseline_kwh: float | None = None
    # 모델이 사용한 입력 월(디버깅/투명성).
    month: int
    model_version: str | None = None
    elapsed_ms: float
    # 합성된 8개 피처(투명성 — 어떤 입력으로 예측했는지 확인용).
    features_used: dict[str, float]

"""피처빌더 — 사용자 의도(에어컨 습관)를 모델의 8개 원시 피처로 변환.

배포된 ML 모델은 "과거 실제 사용량 + 기상"으로 사용량을 예측하는 회귀 모델이라,
프론트(에어컨 습관만 수집)와 입력 계약이 다르다. 이 모듈이 그 간극을 메우는
번역 계층이다. 8개 피처(app/schemas/prediction.py:EXAMPLE_INPUT_ROW)를 만든다:

  - avg_temperature/avg_humidity/total_rainfall : 마포(서울 108) 월별 기후평년값 룩업
  - month_sin/month_cos                         : 월의 삼각함수 인코딩
  - thi                                         : 기온·습도에서 한국 불쾌지수 공식으로 계산
  - prev_year_usage/current_usage               : BASELINE + 에어컨 기여분으로 *추정*

주의: prev_year_usage/current_usage는 실측 검침값이 아니라 추정치다(프론트가 사용량을
수집하지 않음). 따라서 결과는 추정 모델 입력에 기반한 추정이다. 사용량 추정 상수는
프론트 localMockPredict(script.js)와 의도적으로 정합시켜 두 경로의 일관성을 유지한다.
"""

import math

from app.data.seoul_climate import monthly_weather

# --- 사용량 추정 상수 ---
# ⚠️ 동기화 필수: 프론트 azure-app-frontend/script.js 의 USAGE_* 상수 + estimateUsageKwh()
#   와 1:1 일치해야 한다(폴백↔라이브 예측 kWh 정합). 한쪽을 바꾸면 반드시 양쪽을 함께 바꿀 것.
#   별도 레포·무빌드라 모듈 공유 불가 → 이 주석이 유일한 정합 계약(검증: scratchpad parity_check).
BASE_MONTHLY_KWH = 132.0  # 에어컨 외 기저 사용량(원룸 1인). 프론트 USAGE_BASE_MONTHLY_KWH와 동일.
DAYS_PER_MONTH = 30
# 에어컨 타입별 기본 소비전력(W) — 사용자가 전력을 모를 때의 대체값.
TYPE_DEFAULT_POWER_W: dict[str, int] = {
    "fixed": 760,
    "inverter": 560,
    "unknown": 650,
    "none": 0,
}
# 에어컨 타입별 가동 효율 배수(인버터는 듀티사이클로 저감, 정속형은 가중).
TYPE_MULTIPLIER: dict[str, float] = {
    "fixed": 1.1,
    "inverter": 0.92,
    "unknown": 1.0,
    "none": 0.0,
}
FALLBACK_POWER_W = 650
# 모델 학습 분포를 크게 벗어난 입력 방지용 클램프(프론트와 동일 범위).
USAGE_MIN_KWH = 85.0
USAGE_MAX_KWH = 650.0


def compute_thi(temp_c: float, humidity_pct: float) -> float:
    """한국 불쾌지수(THI). 모델의 thi 피처와 동일한 정의.

    THI = 1.8T − 0.55·(1 − RH)·(1.8T − 26) + 32   (T: °C, RH: 0~1 비율)
    운영 모델의 EXAMPLE_INPUT_ROW(T=-0.46, RH=66.55% → thi=36.1077)를 역산해 확인한 식.
    """
    rh = humidity_pct / 100.0
    return 1.8 * temp_c - 0.55 * (1.0 - rh) * (1.8 * temp_c - 26.0) + 32.0


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def estimate_usage(
    aircon_hours_per_day: float,
    aircon_power_w: float | None,
    aircon_type: str,
) -> tuple[float, float]:
    """(prev_year_usage, current_usage) 추정치 반환.

    prev_year_usage = 기저 사용량(에어컨 델타 없는 작년 동월 기준값).
    current_usage   = 기저 + 올해 에어컨 습관 기여분.
    """
    default_power = TYPE_DEFAULT_POWER_W.get(aircon_type, FALLBACK_POWER_W)
    power_w = aircon_power_w or default_power or FALLBACK_POWER_W
    power_kw = power_w / 1000.0
    multiplier = TYPE_MULTIPLIER.get(aircon_type, 1.0)

    aircon_kwh = aircon_hours_per_day * DAYS_PER_MONTH * power_kw * multiplier
    if 0 < aircon_hours_per_day <= 1:
        aircon_kwh += 8  # 단시간 가동의 고정 점화/대기 비용(프론트와 동일 보정).

    current = _clamp(BASE_MONTHLY_KWH + aircon_kwh, USAGE_MIN_KWH, USAGE_MAX_KWH)
    prev_year = BASE_MONTHLY_KWH
    return round(prev_year, 2), round(current, 2)


def build_features(
    *,
    month: int,
    aircon_hours_per_day: float,
    aircon_power_w: float | None,
    aircon_type: str,
) -> dict[str, float]:
    """모델 입력 1행(8개 피처)을 만든다. 키는 EXAMPLE_INPUT_ROW와 일치."""
    avg_temperature, avg_humidity, total_rainfall = monthly_weather(month)
    prev_year_usage, current_usage = estimate_usage(
        aircon_hours_per_day, aircon_power_w, aircon_type
    )
    angle = 2.0 * math.pi * month / 12.0
    return {
        "prev_year_usage": prev_year_usage,
        "avg_temperature": avg_temperature,
        "avg_humidity": avg_humidity,
        "total_rainfall": total_rainfall,
        "current_usage": current_usage,
        "thi": round(compute_thi(avg_temperature, avg_humidity), 7),
        "month_sin": round(math.sin(angle), 12),
        "month_cos": round(math.cos(angle), 12),
    }

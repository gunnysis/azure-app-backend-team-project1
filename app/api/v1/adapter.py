"""어댑터 라우터 — 사용자 의도(에어컨 습관) → 예측.

정적 프론트(찌릿)가 직접 호출하는 엔드포인트. 원시 `/api/v1/predict`와 달리
**API Key를 요구하지 않는다**(브라우저에 키를 둘 수 없으므로). 대신 CORS 출처
화이트리스트(app/main.py)와 rate limit으로 보호한다. 내부적으로 8개 피처를
합성한 뒤 기존 PredictionService를 그대로 재사용한다(ML 경로 단일화).
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends
from starlette.requests import Request

from app.api.deps import get_prediction_service
from app.config import get_settings
from app.core.errors import MLTimeoutError, UpstreamError
from app.core.ratelimit import limiter
from app.schemas.adapter import EstimateRequest, EstimateResponse
from app.schemas.errors import ErrorResponse
from app.schemas.prediction import PredictRequest
from app.services.feature_builder import build_features
from app.services.prediction import PredictionService

# 한국 표준시 — "현재 월" 기본값 산정 기준(App Service는 UTC로 동작할 수 있음).
KST = timezone(timedelta(hours=9))

# 원시 예측 라우터와 달리 인증 의존성이 없다(무키). prefix는 동일 버전 네임스페이스.
router = APIRouter(
    prefix="/api/v1",
    tags=["estimate"],
    responses={
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
    },
)


def _coerce_score(value: Any) -> float:
    """모델 응답의 점수 1건을 float로 정규화한다.

    Azure Designer는 점수를 dict로 감싸 줄 수 있다("Scored Labels" 등).
    """
    if isinstance(value, dict):
        for key in ("Scored Labels", "scored_labels", "prediction", "result"):
            if key in value:
                value = value[key]
                break
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise UpstreamError(
            "ML response prediction was not numeric.", detail={"value": value}
        ) from exc


@router.post("/estimate", response_model=EstimateResponse)
@limiter.limit(get_settings().rate_limit)
async def estimate(
    request: Request,  # slowapi 데코레이터가 요구하는 인자.
    payload: EstimateRequest,
    service: PredictionService = Depends(get_prediction_service),
) -> EstimateResponse:
    settings = get_settings()
    month = payload.month or datetime.now(KST).month
    features = build_features(
        month=month,
        aircon_hours_per_day=payload.aircon_hours_per_day,
        aircon_power_w=payload.aircon_power_w,
        aircon_type=payload.aircon_type,
    )
    # baseline = 같은 월·기상에서 '에어컨 OFF' 가정의 사용량(계절성 기준선). 별도 ML 호출이
    # 아니라 같은 요청에 2행으로 동봉 → predictions[0]=사용자, predictions[1]=기준선.
    # (Azure 스코어링은 입력 행당 출력 행 1개. 추가 호출·과금 없음.)
    baseline_features = build_features(
        month=month, aircon_hours_per_day=0, aircon_power_w=0, aircon_type="none"
    )

    # 총 wall-clock 예산 강제: httpx per-operation 타임아웃은 재시도 누적 시 프론트 abort(8s)를
    # 넘길 수 있다. asyncio.timeout 초과 시 진행 중인 업스트림 요청이 취소(재시도 낭비 차단)되고
    # 즉시 504(ML_TIMEOUT) → 프론트는 graceful fallback. 예산은 프론트 abort보다 낮게 설정.
    try:
        async with asyncio.timeout(settings.estimate_ml_deadline_s):
            result = await service.predict(
                PredictRequest(inputs=[features, baseline_features])
            )
    except TimeoutError as exc:
        raise MLTimeoutError() from exc

    if not result.predictions:
        raise UpstreamError("ML response contained no predictions.")
    predicted_kwh = round(_coerce_score(result.predictions[0]), 2)
    # baseline 행이 비면(모델이 행 1개만 반환 등) None → 프론트가 기본 기준값으로 폴백.
    baseline_kwh = (
        round(_coerce_score(result.predictions[1]), 2)
        if len(result.predictions) > 1
        else None
    )
    return EstimateResponse(
        predicted_kwh=predicted_kwh,
        baseline_kwh=baseline_kwh,
        month=month,
        model_version=result.model_version,
        elapsed_ms=result.elapsed_ms,
        features_used=features,
    )

"""어댑터 라우터 — 사용자 의도(에어컨 습관) → 예측.

정적 프론트(찌릿)가 직접 호출하는 엔드포인트. 원시 `/api/v1/predict`와 달리
**API Key를 요구하지 않는다**(브라우저에 키를 둘 수 없으므로). 대신 CORS 출처
화이트리스트(app/main.py)와 rate limit으로 보호한다. 내부적으로 8개 피처를
합성한 뒤 기존 PredictionService를 그대로 재사용한다(ML 경로 단일화).
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from starlette.requests import Request

from app.api.deps import get_prediction_service
from app.config import get_settings
from app.core.errors import UpstreamError
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


def _extract_predicted_kwh(predictions: list) -> float:
    """모델 응답에서 단일 예측 kWh를 추출한다(행 1건 입력 → 점수 1건)."""
    if not predictions:
        raise UpstreamError("ML response contained no predictions.")
    value = predictions[0]
    # Azure Designer는 점수를 dict로 감싸 줄 수 있다("Scored Labels" 등).
    if isinstance(value, dict):
        for key in ("Scored Labels", "scored_labels", "prediction", "result"):
            if key in value:
                value = value[key]
                break
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise UpstreamError(
            "ML response prediction was not numeric.", detail={"value": predictions[0]}
        ) from exc


@router.post("/estimate", response_model=EstimateResponse)
@limiter.limit(get_settings().rate_limit)
async def estimate(
    request: Request,  # slowapi 데코레이터가 요구하는 인자.
    payload: EstimateRequest,
    service: PredictionService = Depends(get_prediction_service),
) -> EstimateResponse:
    month = payload.month or datetime.now(KST).month
    features = build_features(
        month=month,
        aircon_hours_per_day=payload.aircon_hours_per_day,
        aircon_power_w=payload.aircon_power_w,
        aircon_type=payload.aircon_type,
    )
    result = await service.predict(PredictRequest(inputs=[features]))
    predicted_kwh = _extract_predicted_kwh(result.predictions)
    return EstimateResponse(
        predicted_kwh=round(predicted_kwh, 2),
        month=month,
        model_version=result.model_version,
        elapsed_ms=result.elapsed_ms,
        features_used=features,
    )

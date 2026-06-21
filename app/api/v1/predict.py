"""예측 라우터 — API Key 인증 + Rate limit 적용."""

from fastapi import APIRouter, Depends
from starlette.requests import Request

from app.api.deps import get_prediction_service, verify_api_key
from app.config import get_settings
from app.core.ratelimit import limiter
from app.schemas.errors import ErrorResponse
from app.schemas.prediction import PredictRequest, PredictResponse
from app.services.prediction import PredictionService

router = APIRouter(
    prefix="/api/v1",
    tags=["prediction"],
    dependencies=[Depends(verify_api_key)],
    responses={
        401: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
    },
)


@router.post("/predict", response_model=PredictResponse)
@limiter.limit(get_settings().rate_limit)
async def predict(
    request: Request,  # slowapi 데코레이터가 요구하는 인자.
    payload: PredictRequest,
    service: PredictionService = Depends(get_prediction_service),
) -> PredictResponse:
    return await service.predict(payload)

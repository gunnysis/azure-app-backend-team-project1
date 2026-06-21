"""FastAPI 의존성: API Key 인증, ML 클라이언트/서비스 주입."""

import secrets

from fastapi import Depends, Security
from fastapi.security import APIKeyHeader
from starlette.requests import Request

from app.config import Settings, get_settings
from app.core.errors import UnauthorizedError
from app.ml.base import MLClient
from app.services.prediction import PredictionService

# auto_error=False: 누락 시 403을 자동 발생시키지 않고 우리가 직접 401로 처리.
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    provided: str | None = Security(_api_key_header),
    settings: Settings = Depends(get_settings),
) -> None:
    # 상수 시간 비교로 타이밍 공격 방지.
    if not provided or not secrets.compare_digest(provided, settings.api_key):
        raise UnauthorizedError()


def get_ml_client(request: Request) -> MLClient:
    # lifespan 에서 생성해 app.state 에 보관한 단일 인스턴스를 재사용.
    return request.app.state.ml_client


def get_prediction_service(
    ml_client: MLClient = Depends(get_ml_client),
) -> PredictionService:
    return PredictionService(ml_client)

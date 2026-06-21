"""PredictionService — BFF 로직 계층.

현재는 ML 클라이언트로의 얇은 위임이지만, 향후 요청 가공·응답 재구성 등
프론트 친화적 로직이 들어갈 자리다. 라우터는 이 서비스만 의존한다.
"""

from app.ml.base import MLClient
from app.schemas.prediction import PredictRequest, PredictResponse


class PredictionService:
    def __init__(self, ml_client: MLClient) -> None:
        self._ml = ml_client

    async def predict(self, request: PredictRequest) -> PredictResponse:
        return await self._ml.predict(request)

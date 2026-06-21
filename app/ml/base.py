"""ML 클라이언트 추상 인터페이스.

ML 호출의 유일한 접점. 구현체(Mock/Azure)는 이 인터페이스만 만족하면
서비스·라우터를 바꾸지 않고 교체할 수 있다.
"""

from abc import ABC, abstractmethod

from app.schemas.prediction import PredictRequest, PredictResponse


class MLClient(ABC):
    @abstractmethod
    async def predict(self, request: PredictRequest) -> PredictResponse:
        """예측 수행."""

    @abstractmethod
    async def health(self) -> bool:
        """엔드포인트 도달 가능 여부."""

    async def aclose(self) -> None:
        """리소스 정리 (기본 no-op). httpx 클라이언트 등을 닫을 때 override."""
        return None

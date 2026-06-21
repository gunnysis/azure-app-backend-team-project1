"""설정값에 따라 ML 클라이언트 구현체를 생성한다."""

from app.config import Settings
from app.ml.base import MLClient
from app.ml.mock import MockMLClient


def create_ml_client(settings: Settings) -> MLClient:
    if settings.ml_client == "azure":
        # azure 구현은 httpx 의존 → 필요한 경우에만 지연 import.
        from app.ml.azure import AzureMLClient

        return AzureMLClient(settings)
    return MockMLClient()

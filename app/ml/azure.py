"""AzureMLClient — Azure ML Managed Online Endpoint 호출 (골격).

공식 호출 규약: POST {scoring_uri}, Authorization: Bearer {key}, Content-Type: application/json.
실제 엔드포인트 정보(URI/key)와 입출력 스키마가 확정되면:
  - .env 의 AZURE_ML_SCORING_URI / AZURE_ML_KEY 설정
  - _to_aml_payload / _from_aml_response 두 함수만 수정
하면 나머지 계층은 변경 없이 동작한다.
"""

import asyncio
import time
from typing import Any

import httpx

from app.config import Settings
from app.core.errors import MLTimeoutError, MLUnavailableError, UpstreamError
from app.ml.base import MLClient
from app.schemas.prediction import PredictRequest, PredictResponse


class AzureMLClient(MLClient):
    def __init__(self, settings: Settings) -> None:
        if not settings.azure_ml_scoring_uri or not settings.azure_ml_key:
            raise ValueError(
                "ML_CLIENT=azure 인데 AZURE_ML_SCORING_URI 또는 AZURE_ML_KEY 가 비어 있습니다."
            )
        self._uri = settings.azure_ml_scoring_uri
        self._max_retries = settings.ml_max_retries
        timeout = httpx.Timeout(
            connect=settings.ml_timeout_connect,
            read=settings.ml_timeout_read,
            write=settings.ml_timeout_read,
            pool=settings.ml_timeout_connect,
        )
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {settings.azure_ml_key}",
                "Content-Type": "application/json",
            },
        )

    # --- 스키마 변환 격리 지점 (실제 엔드포인트 확정 시 여기만 수정) ---
    @staticmethod
    def _to_aml_payload(request: PredictRequest) -> dict[str, Any]:
        return {"input_data": request.inputs}

    @staticmethod
    def _from_aml_response(data: Any) -> list[Any]:
        if isinstance(data, dict) and "predictions" in data:
            return data["predictions"]
        return data if isinstance(data, list) else [data]

    async def predict(self, request: PredictRequest) -> PredictResponse:
        payload = self._to_aml_payload(request)
        start = time.perf_counter()
        last_exc: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                resp = await self._client.post(self._uri, json=payload)
            except httpx.TimeoutException as exc:
                last_exc = exc
            except httpx.HTTPError as exc:
                last_exc = exc
            else:
                if resp.status_code < 400:
                    elapsed = (time.perf_counter() - start) * 1000
                    return PredictResponse(
                        predictions=self._from_aml_response(resp.json()),
                        model_version=resp.headers.get("azureml-model-version"),
                        elapsed_ms=round(elapsed, 3),
                    )
                if resp.status_code < 500:
                    # 4xx 는 클라이언트 측 문제 → 재시도 무의미, 즉시 전달.
                    raise UpstreamError(
                        message=f"ML endpoint returned {resp.status_code}.",
                        detail=_safe_body(resp),
                    )
                # 5xx 는 일시적일 수 있음 → 재시도 대상.
                last_exc = UpstreamError(detail={"status": resp.status_code})

            # 마지막 시도가 아니면 지수 백오프 후 재시도.
            if attempt < self._max_retries:
                await asyncio.sleep(0.2 * (2**attempt))

        if isinstance(last_exc, httpx.TimeoutException):
            raise MLTimeoutError() from last_exc
        raise MLUnavailableError(
            detail=str(last_exc) if last_exc else None
        ) from last_exc

    async def health(self) -> bool:
        # 관리형 엔드포인트는 표준 health 경로가 없어, 도달성만 보수적으로 보고한다.
        # (실제 운영에선 가벼운 ping 페이로드로 교체 가능)
        return True

    async def aclose(self) -> None:
        await self._client.aclose()


def _safe_body(resp: httpx.Response) -> Any:
    """업스트림 에러 본문을 안전하게 추출 (JSON 우선, 실패 시 일부 텍스트)."""
    try:
        return resp.json()
    except Exception:
        return resp.text[:500]

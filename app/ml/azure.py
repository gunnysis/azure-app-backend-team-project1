"""AzureMLClient — Azure ML Designer 실시간 엔드포인트(ACI, classic) 호출.

호출 규약(test4 swagger 로 검증): POST {scoring_uri},
Authorization: Bearer {key}, Content-Type: application/json.
입출력은 Designer 웹서비스 형식:
  요청  {"Inputs": {"input1": [ {피처...} ]}, "GlobalParameters": {}}
  응답  {"Results": {"WebServiceOutput0": [ {피처..., "Scored Labels": ...} ]}}
스키마가 바뀌면 _to_aml_payload / _from_aml_response 두 함수만 수정하면 된다.

인증 키는 엔드포인트 단위 primary/secondary 키다(워크스페이스 단일 키 아님).
참고: ACI 엔드포인트는 http(평문)라 Bearer 키가 평문 전송된다 — HTTPS 전환은 내부 사정으로
현재 범위 제외(테스트용 수용). 키 노출 최소화(로그·커밋 금지)로 보완.
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
                "ML_CLIENT=azure 인데 AZURE_ML_SCORING_URI 또는 "
                "AZURE_ML_AUTH_PRI_KEY/SEC_KEY 가 비어 있습니다."
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

    # --- 스키마 변환 격리 지점 (스키마 변경 시 여기만 수정) ---
    @staticmethod
    def _to_aml_payload(request: PredictRequest) -> dict[str, Any]:
        # 검증된 계약(test4 swagger): Designer 실시간 웹서비스 형식.
        # 입력 포트명은 classic Designer 기본값 'input1'.
        return {"Inputs": {"input1": request.inputs}, "GlobalParameters": {}}

    @staticmethod
    def _from_aml_response(data: Any) -> list[Any]:
        # 응답: {"Results": {"WebServiceOutput0": [ {..., "Scored Labels": ...} ]}}
        # ① 출력 포트명에 의존하지 않고 행 배열을 찾는다(모델 교체 내성).
        # ② 각 행에서 예측값('Scored Labels')만 추출 → Mock 과 동일한 list[점수] 형태로 통일.
        #    'Scored Labels' 가 없으면(모델/스키마 교체 등) 행 전체를 보존한다.
        if isinstance(data, dict) and isinstance(data.get("Results"), dict):
            rows = next(
                (v for v in data["Results"].values() if isinstance(v, list)), [data]
            )
        elif isinstance(data, list):
            rows = data
        else:
            rows = [data]
        return [
            row["Scored Labels"]
            if isinstance(row, dict) and "Scored Labels" in row
            else row
            for row in rows
        ]

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
        # 엔드포인트는 GET / → "Healthy"(Bearer 필요) 헬스 경로를 제공하나,
        # /health 마다 업스트림을 ping 하면 부하·과금이 늘어 보수적으로 도달성만 보고한다.
        # (필요 시 base_url + "/" 로 가벼운 GET ping 으로 교체 가능)
        return True

    async def aclose(self) -> None:
        await self._client.aclose()


def _safe_body(resp: httpx.Response) -> Any:
    """업스트림 에러 본문을 안전하게 추출 (JSON 우선, 실패 시 일부 텍스트)."""
    try:
        return resp.json()
    except Exception:
        return resp.text[:500]

"""MockMLClient — 인프로세스 스텁 (별도 Mock 서버/API 아님).

실제 엔드포인트 없이 라우팅·검증·인증·에러·테스트 전 구간을 구동하기 위한 용도.
입력에 대해 결정적(deterministic) 가짜 예측을 반환해 테스트 재현성을 보장한다.
"""

import hashlib
import time

from app.ml.base import MLClient
from app.schemas.prediction import PredictRequest, PredictResponse


class MockMLClient(MLClient):
    async def predict(self, request: PredictRequest) -> PredictResponse:
        start = time.perf_counter()
        # 입력을 정규화해 해시 → 0..1 점수. 같은 입력엔 항상 같은 결과.
        raw = repr(request.inputs).encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        score = int(digest[:8], 16) / 0xFFFFFFFF
        elapsed = (time.perf_counter() - start) * 1000
        return PredictResponse(
            predictions=[round(score, 6)],
            model_version="mock-1.0",
            elapsed_ms=round(elapsed, 3),
        )

    async def health(self) -> bool:
        return True

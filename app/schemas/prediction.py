"""예측 요청/응답 스키마 (Pydantic v2).

실제 ML 엔드포인트의 입출력 형태가 확정되면 이 파일과
app/ml/azure.py 의 변환 함수만 수정하면 된다 (라우터·서비스 불변).
"""

from typing import Any

from pydantic import BaseModel, ConfigDict


class PredictRequest(BaseModel):
    # 알 수 없는 필드는 거부 → 오타·오용을 조기에 422로 차단.
    model_config = ConfigDict(extra="forbid")

    # 실제 스키마 확정 시 구체화. 현재는 추상 인터페이스 형태.
    inputs: list[float] | dict[str, Any]


class PredictResponse(BaseModel):
    # 'model_'로 시작하는 필드는 Pydantic v2 보호 네임스페이스와 충돌하여
    # 경고가 발생하므로 protected_namespaces=() 로 명시 해제한다.
    model_config = ConfigDict(protected_namespaces=())

    predictions: list[Any]
    model_version: str | None = None
    elapsed_ms: float

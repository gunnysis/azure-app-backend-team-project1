"""예측 요청/응답 스키마 (Pydantic v2).

입력 계약은 운영 엔드포인트(`final-endpoint`) swagger 로 검증됨 (Designer 실시간 웹서비스):
요청 본문은 행(레코드)들의 배열이며, AzureMLClient 가 이를
`{"Inputs": {"input1": [...]}, "GlobalParameters": {}}` 로 감싼다.
모델이 교체될 수 있어 피처를 코드에 못박지 않고 제네릭 dict 로 둔다(§0.1).
스키마가 바뀌어도 이 파일과 app/ml/azure.py 변환 함수만 수정하면 된다(라우터·서비스 불변).

`EXAMPLE_INPUT_ROW` 는 샘플 페이로드의 **단일 진실원**이다 — Swagger 예시·테스트·
스모크 스크립트(app/ml/comsume.py)가 모두 이 상수를 재사용한다. 계약(피처명/값)이
바뀌면 여기 한 곳만 고치면 전 사용처에 반영된다(과거엔 5곳에 중복되어 드리프트 발생).
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# 운영 계약(final-endpoint swagger) 입력 1행, 8개 피처. 샘플의 단일 진실원.
# (test4 대비 변경: avg_temp→avg_temperature, prev_year_usage·current_usage int64→double)
EXAMPLE_INPUT_ROW: dict[str, Any] = {
    "prev_year_usage": 76,
    "avg_temperature": -0.46,
    "avg_humidity": 66.55,
    "total_rainfall": 21.1,
    "current_usage": 53,
    "thi": 36.1076813,
    "month_sin": 0.5,
    "month_cos": 0.8660254037844387,
}


class PredictRequest(BaseModel):
    # 알 수 없는 최상위 필드는 거부 → 오타·오용을 조기에 422로 차단.
    # json_schema_extra: Swagger /docs 의 예시도 단일 진실원(EXAMPLE_INPUT_ROW)에서 파생.
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"inputs": [EXAMPLE_INPUT_ROW]}},
    )

    # 행 배열(각 행 = 피처명→값). 빈 배열은 무의미하므로 1건 이상 요구.
    inputs: list[dict[str, Any]] = Field(min_length=1)


class PredictResponse(BaseModel):
    # 'model_'로 시작하는 필드는 Pydantic v2 보호 네임스페이스와 충돌하여
    # 경고가 발생하므로 protected_namespaces=() 로 명시 해제한다.
    model_config = ConfigDict(protected_namespaces=())

    predictions: list[Any]
    model_version: str | None = None
    elapsed_ms: float

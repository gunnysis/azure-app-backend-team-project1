"""configure_observability 의 no-op 경로 + OTel 계측 회귀 검증.

1) 연결문자열 없으면 예외 없이 비활성(False) — 모든 비-App-Insights 환경 보호.
2) OTel FastAPI 계측 0.61b0 의 405→500 버그 가드 회귀:
   `_get_route_details` 는 `Match.PARTIAL`(경로 일치·메서드 불일치 = HTTP 405)
   분기에서 `route.path` 접근을 try/except 로 감싸지 않아, `include_router(prefix=...)`
   로 들어온 `_IncludedRouter`(.path 없음) 매칭 시 AttributeError → 요청이 500/502 로
   떨어진다. 운영(App Insights 활성)에서만 발현해 평시 pytest(계측 미적용)가 놓쳤다.
   아래 테스트는 연결문자열/익스포터 없이 `instrument_app` 만 적용해 버그 경로를
   재현하고, 가드가 405 를 500 으로 만들지 않음을 고정한다(가드 제거 시 500 실패).
"""

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from app.config import Settings
from app.observability import (
    _install_otel_partial_match_guard,
    configure_observability,
)


def test_no_op_without_connection_string():
    # _env_file=None 으로 .env 파일 격리. (conftest 가 env 를 ""로 두므로 falsy)
    settings = Settings(_env_file=None)
    app = FastAPI()
    assert not settings.applicationinsights_connection_string  # None 또는 "" (falsy)
    assert configure_observability(app, settings) is False  # 예외 없이 no-op


def _instrumented_app() -> FastAPI:
    # 운영과 동일하게 prefix 라우터를 include → 매칭 객체가 _IncludedRouter(.path 없음).
    router = APIRouter(prefix="/api/v1")

    @router.post("/predict")
    async def _predict() -> dict[str, bool]:
        return {"ok": True}

    app = FastAPI()
    app.include_router(router)
    FastAPIInstrumentor.instrument_app(app)
    return app


def test_method_mismatch_returns_405_not_500_under_otel():
    _install_otel_partial_match_guard()  # 멱등 — 미들웨어 구성 전 모듈 전역 가드 설치
    app = _instrumented_app()
    try:
        client = TestClient(app, raise_server_exceptions=False)
        # 경로는 존재하나 메서드 불일치(GET) = PARTIAL 매치 = 버그 트리거 지점.
        assert client.get("/api/v1/predict").status_code == 405
        # CORS preflight(OPTIONS) 도 같은 경로 — 500 이 아니어야 한다.
        assert client.options("/api/v1/predict").status_code != 500
    finally:
        FastAPIInstrumentor.uninstrument_app(app)


def test_guard_is_idempotent():
    # 여러 앱 인스턴스(워커/재구성)에서 반복 호출돼도 중첩 래핑되지 않아야 한다.
    import app.observability as obs

    _install_otel_partial_match_guard()
    _install_otel_partial_match_guard()
    assert obs._route_detail_guard_installed is True

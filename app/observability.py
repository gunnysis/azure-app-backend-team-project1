"""Azure Monitor(Application Insights) 연동 — 연결문자열이 있을 때만 활성, 없으면 no-op.

설계 의도(재발방지):
- `APPLICATIONINSIGHTS_CONNECTION_STRING` 이 있을 때만 동작. 미설정(로컬/테스트/미승인)에선
  **완전 no-op** — 무거운 OTel import 조차 회피(지연 import). 어떤 환경도 깨지지 않는다.
- **명시적 계측**: distro 자동계측에 의존하지 않고 `instrument_app(app)`/`HTTPXClientInstrumentor`
  를 직접 호출한다. (자동계측은 환경/호출순서에 따라 FastAPI 요청·httpx 의존성 span 이
  누락되는 사례가 있었음 — traces 만 들어오고 requests/dependencies 가 비는 증상.)
- provider 구성(configure_azure_monitor)·httpx 계측·로그억제는 **프로세스당 1회**,
  FastAPI 계측은 **앱 인스턴스마다** 적용.
"""

import logging

from fastapi import FastAPI

from app.config import Settings

logger = logging.getLogger("app")

_provider_configured = False
_route_detail_guard_installed = False


def _install_otel_partial_match_guard() -> None:
    """OTel FastAPI 계측(0.61b0)의 405 → 500 버그 우회 (재발방지, 멱등).

    `_get_route_details` 는 `Match.FULL` 분기에서만 `route.path` 접근을 try/except 로
    감싸고 `Match.PARTIAL`(경로는 맞고 메서드는 불일치 = HTTP 405) 분기는 가드가 없다.
    `include_router(prefix=...)` 로 들어온 라우트는 `.path` 없는 `_IncludedRouter` 라
    405·CORS preflight(OPTIONS)·일부 헬스 프로브에서 `AttributeError` 가 나고, 이게
    OTel ASGI 미들웨어(최외곽)에서 터져 요청 자체가 502/500 으로 떨어진다.

    `instrument_app` 이 이 버전에선 `default_span_details` 콜백을 노출하지 않으므로,
    미들웨어가 참조하는 모듈 전역 `_get_default_span_details` 를 방어적으로 감싼다.
    텔레메트리 span 이름 계산은 부가 기능이라 실패해도 요청을 깨선 안 된다 — 실패 시
    메서드명으로 폴백한다. (업스트림 수정 반영 시 이 가드 제거 가능.)
    """
    global _route_detail_guard_installed
    if _route_detail_guard_installed:
        return
    import opentelemetry.instrumentation.fastapi as otel_fastapi

    original = otel_fastapi._get_default_span_details

    def _safe_span_details(scope):  # type: ignore[no-untyped-def]
        try:
            return original(scope)
        except Exception:  # noqa: BLE001 — 텔레메트리가 요청을 깨뜨리지 않도록 광범위 포착
            return (scope.get("method") or "HTTP"), {}

    otel_fastapi._get_default_span_details = _safe_span_details
    _route_detail_guard_installed = True


def configure_observability(app: FastAPI, settings: Settings) -> bool:
    """App Insights 텔레메트리 구성+계측. 활성화되면 True, no-op면 False."""
    connection_string = settings.applicationinsights_connection_string
    if not connection_string:
        logger.info("Application Insights 비활성(연결문자열 미설정) — 텔레메트리 no-op")
        return False

    # 지연 import: 연결문자열이 없는 환경에선 OTel 의존성을 로드하지 않는다.
    from azure.monitor.opentelemetry import configure_azure_monitor
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

    global _provider_configured
    if not _provider_configured:
        configure_azure_monitor(
            connection_string=connection_string,
            logger_name="app",  # 앱 로거 로그를 App Insights(traces)로 수집
        )
        # ML 호출(httpx) → dependency telemetry (지연/실패/재시도 가시화).
        HTTPXClientInstrumentor().instrument()
        # 재발방지: Azure SDK 가 telemetry 송신마다 HTTP 로그를 INFO 로 도배 → WARNING 으로 억제.
        for noisy in (
            "azure.core.pipeline.policies.http_logging_policy",
            "azure.monitor.opentelemetry.exporter",
        ):
            logging.getLogger(noisy).setLevel(logging.WARNING)
        _provider_configured = True

    # 재발방지: OTel 405→500 버그 가드를 instrument_app 전에 설치(미들웨어가 구성 시점에
    # 모듈 전역 _get_default_span_details 를 캡처하므로 반드시 계측 이전이어야 한다).
    _install_otel_partial_match_guard()

    # FastAPI 요청 추적: 앱 인스턴스에 명시 계측(자동계측 누락 방지).
    FastAPIInstrumentor.instrument_app(app)
    logger.info("Application Insights 활성화 — FastAPI/httpx/logging 계측")
    return True

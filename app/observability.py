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

    # FastAPI 요청 추적: 앱 인스턴스에 명시 계측(자동계측 누락 방지).
    FastAPIInstrumentor.instrument_app(app)
    logger.info("Application Insights 활성화 — FastAPI/httpx/logging 계측")
    return True

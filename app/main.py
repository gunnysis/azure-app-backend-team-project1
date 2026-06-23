"""FastAPI 애플리케이션 진입점.

create_app() 에서 lifespan(ML 클라이언트 수명주기), 미들웨어, 라우터,
예외 핸들러를 등록한다. App Service startup: `app.main:app`.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.api.v1 import adapter, health, predict
from app.config import get_settings
from app.core.exception_handlers import build_error_body, register_exception_handlers
from app.core.middleware import RequestContextMiddleware
from app.core.ratelimit import limiter
from app.ml.factory import create_ml_client
from app.observability import configure_observability

logger = logging.getLogger("app")


async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    rid = getattr(request.state, "request_id", None)
    body = build_error_body(
        "RATE_LIMITED", f"Rate limit exceeded: {exc.detail}", rid
    )
    return JSONResponse(status_code=429, content=body)


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # 워커마다 1회 실행 → 워커별 단일 ML 클라이언트(커넥션 풀 재사용).
        app.state.ml_client = create_ml_client(settings)
        logger.info("ML client initialized: %s", settings.ml_client)
        try:
            yield
        finally:
            await app.state.ml_client.aclose()
            logger.info("ML client closed")

    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    # --- Rate limiter 연결 ---
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

    # --- 예외 핸들러 ---
    register_exception_handlers(app)

    # --- 라우터 ---
    app.include_router(health.router)
    app.include_router(predict.router)
    app.include_router(adapter.router)

    # --- 미들웨어 (나중에 추가한 것이 바깥=먼저 실행) ---
    # CORS: 허용 출처가 명시된 경우에만 활성화.
    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Request-ID"],
        )
    # RequestContext 를 가장 마지막에 추가 → 가장 바깥에서 request_id 발급.
    app.add_middleware(RequestContextMiddleware)

    # App Insights 텔레메트리(연결문자열 있을 때만, 없으면 no-op). 앱·미들웨어 구성 후
    # 명시적으로 계측한다(FastAPI 요청 + httpx ML 호출 + 로그).
    configure_observability(app, settings)

    return app


app = create_app()

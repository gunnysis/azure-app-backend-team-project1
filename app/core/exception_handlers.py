"""전역 예외 핸들러 — 모든 에러를 동일한 표준 포맷으로 변환한다.

포맷: {"error": {"code", "message", "request_id", "detail"}}
내부 예외 메시지·스택은 클라이언트에 노출하지 않는다(로그에만).
"""

import logging
from typing import Any

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request

from app.core.errors import AppError

logger = logging.getLogger("app.error")


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def build_error_body(
    code: str, message: str, request_id: str | None, detail: Any = None
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
            "detail": detail,
        }
    }


def _json_error(
    status_code: int, code: str, message: str, request_id: str | None, detail: Any = None
) -> JSONResponse:
    # jsonable_encoder 로 detail(검증 오류 등) 안의 비직렬화 객체를 안전 변환.
    body = jsonable_encoder(build_error_body(code, message, request_id, detail))
    return JSONResponse(status_code=status_code, content=body)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    rid = _request_id(request)
    logger.warning("AppError code=%s msg=%s rid=%s", exc.code, exc.message, rid)
    return _json_error(exc.http_status, exc.code, exc.message, rid, exc.detail)


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    rid = _request_id(request)
    return _json_error(
        422, "VALIDATION_ERROR", "Request validation failed.", rid, exc.errors()
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    rid = _request_id(request)
    return _json_error(exc.status_code, "HTTP_ERROR", str(exc.detail), rid)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    rid = _request_id(request)
    logger.exception("Unhandled error rid=%s", rid)
    return _json_error(500, "INTERNAL_ERROR", "Internal server error.", rid)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

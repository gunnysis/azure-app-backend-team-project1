"""커스텀 예외 계층. 전역 핸들러가 이를 표준 에러 응답으로 변환한다.

각 예외는 (code, http_status, message)를 갖는다. 비즈니스 코드는
HTTP 상태를 직접 다루지 않고 의미 있는 예외를 raise 한다.
"""

from typing import Any


class AppError(Exception):
    code: str = "INTERNAL_ERROR"
    http_status: int = 500
    message: str = "Internal server error."

    def __init__(self, message: str | None = None, *, detail: Any | None = None) -> None:
        self.message = message or self.message
        self.detail = detail
        super().__init__(self.message)


class UnauthorizedError(AppError):
    code = "AUTH_INVALID"
    http_status = 401
    message = "Invalid or missing API key."


class MLUnavailableError(AppError):
    code = "ML_UNAVAILABLE"
    http_status = 502
    message = "ML endpoint is temporarily unavailable."


class MLTimeoutError(AppError):
    # 타임아웃은 502(Bad Gateway)보다 504(Gateway Timeout)가 의미상 정확하다.
    code = "ML_TIMEOUT"
    http_status = 504
    message = "ML endpoint request timed out."


class UpstreamError(AppError):
    code = "UPSTREAM_ERROR"
    http_status = 502
    message = "ML endpoint returned an error."

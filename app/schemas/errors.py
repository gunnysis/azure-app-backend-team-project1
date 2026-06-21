"""표준 에러 응답 스키마. 모든 에러는 동일한 형태로 직렬화된다."""

from typing import Any

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str | None = None
    detail: Any | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail

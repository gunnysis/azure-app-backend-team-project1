"""Rate limiter (slowapi).

한계(설계 문서 §6): 인메모리 저장소는 gunicorn 멀티워커에서 워커별로 분리되고,
App Service 프록시 뒤에서는 실제 클라이언트 IP가 X-Forwarded-For 에 있다.
따라서 IP 추출은 X-Forwarded-For 우선으로 처리하고, 본 프로젝트에서는
"근사 보호" 수준으로 운용한다(정밀 제한 필요 시 Redis 백엔드로 교체).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.config import get_settings


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # 첫 번째 값이 최초 클라이언트 IP.
        return forwarded.split(",")[0].strip()
    return get_remote_address(request) or "anonymous"


_settings = get_settings()
limiter = Limiter(key_func=client_ip, enabled=_settings.rate_limit_enabled)

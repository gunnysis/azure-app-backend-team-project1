"""configure_observability 의 no-op 경로 검증 (연결문자열 없으면 안전).

실제 텔레메트리 전송 경로는 라이브 검증으로 확인한다. 여기선 미설정 시
예외 없이 비활성(False)으로 동작하는지(= 모든 비-App-Insights 환경 보호)만 본다.
"""

from fastapi import FastAPI

from app.config import Settings
from app.observability import configure_observability


def test_no_op_without_connection_string():
    # _env_file=None 으로 .env 파일 격리. (conftest 가 env 를 ""로 두므로 falsy)
    settings = Settings(_env_file=None)
    app = FastAPI()
    assert not settings.applicationinsights_connection_string  # None 또는 "" (falsy)
    assert configure_observability(app, settings) is False  # 예외 없이 no-op

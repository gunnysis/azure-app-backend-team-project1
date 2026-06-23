"""테스트 공통 픽스처.

env 를 먼저 설정한 뒤 app 을 import 해야 한다 (설정이 import 시점에 캐시되므로).
ASGITransport 는 lifespan 을 실행하지 않으므로 ml_client 를 수동 주입한다.
"""

import os

os.environ["ML_CLIENT"] = "mock"
os.environ["API_KEY"] = "test-key"
os.environ["RATE_LIMIT_ENABLED"] = "false"  # 테스트 결정성 확보
os.environ["CORS_ORIGINS"] = ""
# 텔레메트리 비활성: .env 에 연결문자열이 있어도 테스트는 App Insights 로 전송하지 않는다
# (env 값이 .env 보다 우선 → no-op). 테스트 격리·결정성.
os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"] = ""

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402
from app.ml.factory import create_ml_client  # noqa: E402
from app.schemas.prediction import EXAMPLE_INPUT_ROW  # noqa: E402

API_HEADERS = {"X-API-Key": "test-key"}

# 샘플 입력 1행은 스키마의 단일 진실원을 재사용(테스트 간 중복 제거).
SAMPLE_ROW = EXAMPLE_INPUT_ROW


@pytest_asyncio.fixture
async def client():
    app.state.ml_client = create_ml_client(get_settings())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await app.state.ml_client.aclose()

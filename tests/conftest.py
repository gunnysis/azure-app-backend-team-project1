"""테스트 공통 픽스처.

env 를 먼저 설정한 뒤 app 을 import 해야 한다 (설정이 import 시점에 캐시되므로).
ASGITransport 는 lifespan 을 실행하지 않으므로 ml_client 를 수동 주입한다.
"""

import os

os.environ["ML_CLIENT"] = "mock"
os.environ["API_KEY"] = "test-key"
os.environ["RATE_LIMIT_ENABLED"] = "false"  # 테스트 결정성 확보
os.environ["CORS_ORIGINS"] = ""

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402
from app.ml.factory import create_ml_client  # noqa: E402

API_HEADERS = {"X-API-Key": "test-key"}


@pytest_asyncio.fixture
async def client():
    app.state.ml_client = create_ml_client(get_settings())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await app.state.ml_client.aclose()

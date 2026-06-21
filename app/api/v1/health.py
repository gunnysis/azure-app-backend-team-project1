"""헬스체크 — 인증/RateLimit 제외 (App Service 플랫폼 프로브 통과용)."""

from fastapi import APIRouter, Depends

from app.api.deps import get_ml_client
from app.ml.base import MLClient

router = APIRouter(tags=["health"])


@router.get("/health")
async def liveness() -> dict[str, str]:
    """프로세스 생존 여부. App Service Health check 경로로 사용."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(ml_client: MLClient = Depends(get_ml_client)) -> dict[str, object]:
    """ML 백엔드 도달성까지 포함한 준비 상태."""
    ready = await ml_client.health()
    return {"status": "ready" if ready else "degraded", "ml": ready}

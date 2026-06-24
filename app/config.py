"""애플리케이션 설정 — pydantic-settings 기반 (.env 로드).

환경변수는 대소문자 무시로 매핑된다 (예: API_KEY -> api_key).
시크릿 값은 .env 또는 App Service Application Settings로 주입한다 (커밋 금지).
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    app_name: str = "Azure ML Backend"
    environment: str = "development"
    log_level: str = "INFO"

    # --- Auth ---
    api_key: str = Field(default="dev-local-key", description="X-API-Key 기대값")

    # --- ML client 선택 및 Azure ML 연동 ---
    ml_client: str = Field(default="mock", pattern="^(mock|azure)$")
    azure_ml_scoring_uri: str | None = None
    # 엔드포인트 단위 인증 키(워크스페이스 단일 키는 존재하지 않음).
    # primary/secondary 2개가 발급되며, 호출엔 primary 우선·secondary 폴백(회전 대비).
    azure_ml_auth_pri_key: str | None = None
    azure_ml_auth_sec_key: str | None = None
    ml_timeout_connect: float = 5.0
    ml_timeout_read: float = 30.0
    ml_max_retries: int = 2
    # 브라우저용 /api/v1/estimate 의 ML 호출 총 wall-clock 예산(초). httpx 타임아웃은
    # per-operation 이라 재시도×read 가 누적되면 수십 초까지 늘 수 있다(공식 문서 확인).
    # 어댑터가 이 값으로 asyncio.timeout 총 예산을 강제 → 프론트 abort(8s)보다 낮게 두어
    # ① 프론트가 살아있는 백엔드를 선점하지 않고 ② 예산 초과 시 재시도 낭비 없이 즉시 504.
    # (서버-서버용 /api/v1/predict 는 이 예산을 적용하지 않고 전체 재시도 예산을 유지.)
    estimate_ml_deadline_s: float = 6.0

    # --- Observability (Azure Monitor / Application Insights) ---
    # 연결문자열이 있으면 텔레메트리 활성, 없으면 런타임 no-op. (시크릿 — App Settings/.env 주입)
    applicationinsights_connection_string: str | None = None

    # --- CORS ---
    cors_origins: str = ""  # 콤마 구분 (예: "https://a.com,https://b.com")

    # --- Rate limit ---
    rate_limit_enabled: bool = True
    rate_limit: str = "60/minute"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def azure_ml_key(self) -> str | None:
        """Bearer 에 사용할 활성 엔드포인트 키 — primary 우선, 없으면 secondary."""
        return self.azure_ml_auth_pri_key or self.azure_ml_auth_sec_key


@lru_cache
def get_settings() -> Settings:
    """프로세스 당 1회 로드 후 캐시."""
    return Settings()

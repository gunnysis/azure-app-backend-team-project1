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
    azure_ml_key: str | None = None
    ml_timeout_connect: float = 5.0
    ml_timeout_read: float = 30.0
    ml_max_retries: int = 2

    # --- CORS ---
    cors_origins: str = ""  # 콤마 구분 (예: "https://a.com,https://b.com")

    # --- Rate limit ---
    rate_limit_enabled: bool = True
    rate_limit: str = "60/minute"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """프로세스 당 1회 로드 후 캐시."""
    return Settings()

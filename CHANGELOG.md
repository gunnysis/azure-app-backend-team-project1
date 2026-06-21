# Changelog

이 프로젝트의 주요 변경 사항을 기록합니다.
형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/)를 따르며,
버전 체계는 [유의적 버전(SemVer)](https://semver.org/lang/ko/)을 따릅니다.

## [Unreleased]

### 예정 (Planned)
- 실제 Azure ML 엔드포인트 연동 (`AzureMLClient` 변환 함수 2개 + `.env`) — **승인 필요**
- App Service(Code) 배포 — **승인 필요**

---

## [0.1.0] - 2026-06-21

ML 추상화 레이어 기반 FastAPI 백엔드 초기 베이스라인. Mock 구현으로 전 구간 동작·테스트 완료.

### Added
- **ML 추상화 레이어**: `MLClient`(ABC) → `MockMLClient`/`AzureMLClient`, `ML_CLIENT=mock|azure` 스위칭.
  - Mock: 입력 sha256 기반 **결정적** 예측(테스트 재현성).
  - Azure: 골격 구현. 스키마 변환을 `_to_aml_payload`/`_from_aml_response` 2함수로 격리.
- **API 엔드포인트**: `POST /api/v1/predict`, `GET /health`(liveness), `GET /health/ready`(readiness).
- **인증**: `X-API-Key` 헤더, `secrets.compare_digest` 상수시간 비교.
- **검증**: Pydantic v2 요청/응답 스키마(`extra="forbid"`, `protected_namespaces=()`).
- **에러 표준화**: 전역 예외 핸들러 → `{error:{code,message,request_id,detail}}` 통일 포맷.
- **요청 추적**: `X-Request-ID` 생성/승계 미들웨어(응답 헤더·로그).
- **Rate limiting**: slowapi 기반 IP 근사 제한(`X-Forwarded-For` 인지), 기본 `60/minute`.
- **CORS**: `CORS_ORIGINS` 환경변수 기반.
- **설정**: pydantic-settings `Settings`(`.env` 로드), `get_settings()` 캐시.
- **테스트**: pytest 스위트 11건(health/auth/predict/validation), `httpx.ASGITransport` E2E.
- **배포 준비**: `startup.sh`(gunicorn+UvicornWorker:8000), 전체 핀 고정 의존성.
- **문서**: 설계서(design_backend.md v3), PRD/SPEC/TRD, README, CLAUDE.md.

### Security
- `.gitignore` 추가(`.env`, `.venv`, `__pycache__`, `*.zip` 등) 및 커밋되었던 빌드 산출물(`__pycache__`, `deploy.zip`) 추적 해제.
- 시크릿은 `.env`(로컬) / App Service Application Settings(운영)로만 주입, 커밋 금지 원칙 확립.

### Fixed
- Pydantic v2 `model_version` 필드의 보호 네임스페이스(`model_`) 충돌 경고 → `protected_namespaces=()`로 해소.
- 공식 권장 startup에 필요한 `gunicorn` 의존성 누락 → 추가.

[Unreleased]: https://github.com/gunnysis/azure-app-backend-team-project1/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/gunnysis/azure-app-backend-team-project1/releases/tag/v0.1.0

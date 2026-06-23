# Changelog

이 프로젝트의 주요 변경 사항을 기록합니다.
형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/)를 따르며,
버전 체계는 [유의적 버전(SemVer)](https://semver.org/lang/ko/)을 따릅니다.

## [Unreleased]

### 예정 (Planned)
- 실제 ML 스키마 확정 시 `inputs`/`predictions` 구체화 (SPEC 동반 개정).
- Redis 공유 백엔드 기반 전역 정밀 Rate limit(다중 인스턴스 정확성).
- CI(테스트 자동화)·배포 파이프라인.

---

## [0.2.0] - 2026-06-22

실 Azure ML 엔드포인트 연동·운영 배포·관측성을 완료한 릴리스. App Service에서 `ML_CLIENT=azure`로 E2E 동작.

### Added
- **Azure ML Designer 실시간 엔드포인트 실연동**(`AzureMLClient`): test4 swagger로 검증된 Designer 웹서비스 계약 구현.
  - 요청 `{"Inputs":{"input1":[...]},"GlobalParameters":{}}` / 응답 `{"Results":{"WebServiceOutput0":[...]}}`을 변환 2함수(`_to_aml_payload`/`_from_aml_response`)로 격리.
  - 응답에서 `Scored Labels`만 추출해 Mock과 동일한 `list[점수]` 형태로 통일(출력 포트명 비의존 → 모델 교체 내성).
  - 엔드포인트 단위 인증 키 `AZURE_ML_AUTH_PRI_KEY`/`AZURE_ML_AUTH_SEC_KEY`(primary 우선·secondary 폴백, `azure_ml_key` 프로퍼티).
- **운영 배포 자동화**(`deploy.sh`): App Settings 주입 → startup/헬스체크 설정 → zip OneDeploy → 스모크 테스트의 멱등 스크립트. transient 502(false-negative) 내성.
- **관측성**(`app/observability.py`): Azure Monitor(Application Insights) 연동. `APPLICATIONINSIGHTS_CONNECTION_STRING`이 있을 때만 활성, 없으면 완전 no-op(OTel 지연 import). FastAPI/httpx/logging 명시 계측.
- **엔드포인트 스모크 스크립트**(`app/ml/comsume.py`): test4 엔드포인트 단독 점검용 1회성 스크립트(`__main__` 가드, 패키지 import 안 됨).
- **테스트 확충**: 11건 → 23건(azure 클라이언트 변환·재시도·관측성 no-op 등 추가 커버).

### Changed
- **요청 스키마 계약**: `PredictRequest.inputs`를 스칼라/단일 dict 허용에서 **행(dict) 배열**(`list[dict[str, Any]]`, 최소 1건)로 확정. Designer 입력 포트(`input1`) 형식에 정렬.
- **Mock 예측**: 입력 행마다 `sha256(sorted(row.items()))` 기반 점수 1개 반환(행 단위 결정성).
- **startup.sh**: 포트 바인딩을 `${PORT:-8000}`로 하드닝(App Service 주입 포트 우선).

### Security
- ACI(Designer classic) 엔드포인트는 http 평문이라 Bearer 키가 평문 전송됨 — 테스트용 수용, 키 노출 최소화(로그·커밋 금지)로 보완. HTTPS 전환은 현재 범위 외.
- App Insights 연결문자열 등 모든 시크릿은 App Settings/`.env`로만 주입(커밋 금지).

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

[Unreleased]: https://github.com/gunnysis/azure-app-backend-team-project1/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/gunnysis/azure-app-backend-team-project1/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/gunnysis/azure-app-backend-team-project1/releases/tag/v0.1.0

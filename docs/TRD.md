# TRD — 기술 요구사항 / 구현 문서 (Technical Requirements Document)

> 문서 성격: **어떻게 구현했는가**(스택·구조·결정 근거). 외부 계약은 [SPEC](SPEC.md), 요구 배경은 [PRD](PRD.md), 아키텍처 다이어그램·팩트체크 출처는 [design_backend.md](achieve/design_backend.md).
> 버전: 0.1.0 · 최종 수정: 2026-06-21

---

## 1. 기술 스택

| 영역 | 선택 | 버전(핀) | 근거 |
|---|---|---|---|
| 언어 | Python | 3.14 | App Service Linux 정식 지원(2025-10-28) |
| 웹 프레임워크 | FastAPI | 0.137.2 | 비동기·Pydantic v2·OpenAPI 자동화 |
| ASGI 서버 | uvicorn(개발) / gunicorn+UvicornWorker(운영) | 0.49.0 / 26.0.0 | 공식 권장 startup |
| 검증 | Pydantic v2 / pydantic-settings | 2.13.4 / 2.14.2 | 스키마·설정 로드 |
| HTTP 클라이언트 | httpx | 0.28.1 | async, ASGITransport 테스트 공용 |
| Rate limit | slowapi / limits | 0.1.10 / 5.8.0 | 경량 IP 기준 제한 |
| 테스트 | pytest / pytest-asyncio | 9.1.1 / 1.4.0 | 비동기 E2E |

> 런타임은 `requirements.txt`(전이 의존성까지 전체 핀 고정), 개발은 `requirements-dev.txt`(`-r requirements.txt` + 테스트).

## 2. 디렉터리 구조

```
app/
├── main.py                  # create_app(), lifespan, 미들웨어·라우터·핸들러 등록
├── config.py                # Settings(pydantic-settings), get_settings() lru_cache
├── api/
│   ├── deps.py              # verify_api_key, get_ml_client, get_prediction_service
│   └── v1/{health,predict}.py
├── schemas/
│   ├── prediction.py        # PredictRequest / PredictResponse
│   └── errors.py            # ErrorDetail / ErrorResponse
├── services/
│   └── prediction.py        # PredictionService (BFF 위임 계층)
├── ml/
│   ├── base.py              # MLClient(ABC): predict/health/aclose
│   ├── mock.py              # MockMLClient (결정적 인프로세스 스텁)
│   ├── azure.py             # AzureMLClient (골격; 변환 2함수로 스키마 격리)
│   └── factory.py           # create_ml_client(settings)
└── core/
    ├── errors.py            # AppError 계층
    ├── middleware.py        # RequestContextMiddleware (X-Request-ID)
    ├── exception_handlers.py# 전역 예외 → 표준 포맷
    └── ratelimit.py         # Limiter(key_func=client_ip)
```

## 3. 레이어 책임

```
라우터(HTTP 입출력·검증) → 서비스(BFF 가공) → MLClient(추상화) → Azure ML
```

- **라우터**: HTTP 입출력·검증만, 비즈니스 로직 없음.
- **서비스(`PredictionService`)**: 요청 가공 → MLClient 호출 → 응답 가공(현재는 얇은 위임, 프론트 친화 가공 자리).
- **MLClient 추상화**: ML 호출의 **유일한 접점**. `ML_CLIENT` 환경변수로 구현체 스위칭.

## 4. 핵심 설계 결정 (ADR 요약)

| ID | 결정 | 근거 | 대안/트레이드오프 |
|---|---|---|---|
| D1 | ML 호출을 `MLClient` ABC 뒤로 격리 | 실제 정보 없이 본체 완성, 연동 국소화 | 직접 호출 → 결합도↑, 테스트 곤란 |
| D2 | Mock = 인프로세스 스텁(결정적 해시) | 5일 일정, 재현 가능 테스트 | 별도 Mock 서버 → 오버스펙 |
| D3 | Azure 변환을 `_to_aml_payload`/`_from_aml_response` 2함수로 격리 | 스키마 확정 시 변경 최소화 | 라우터/서비스에 분산 → 변경 확산 |
| D4 | startup = gunicorn+UvicornWorker:8000 | App Service 공식 권장 | uvicorn 단독 → 프로세스 관리 약함 |
| D5 | 타임아웃 분리(connect 5s/read 30s) < gunicorn timeout 600s | 워커 행 방지 | 단일 타임아웃 → 행 위험 |
| D6 | 표준 에러 envelope + request_id | 추적성·일관 UX | 프레임워크 기본 에러 → 비일관 |
| D7 | Rate limit 인메모리+XFF "근사 보호" | 비영리·5일 적정 | Redis 공유 → 운영 비용·범위 초과 |
| D8 | ML_TIMEOUT=504, ML_UNAVAILABLE/UPSTREAM=502 | 게이트웨이 의미상 정확 | 모두 502 → 의미 손실 |
| D9 | Stateless 유지(인메모리 상태 의존 금지) | P0v3 오토스케일(다중 인스턴스) 전제 | 세션/캐시 의존 → scale-out 시 불일치 |

## 5. ML 추상화 상세

### 5.1 인터페이스 (`base.py`)
```python
class MLClient(ABC):
    async def predict(self, request: PredictRequest) -> PredictResponse: ...
    async def health(self) -> bool: ...
    async def aclose(self) -> None: ...   # 기본 no-op
```

### 5.2 Mock (`mock.py`)
- `sha256(repr(inputs))` 상위 8자리 → `0xFFFFFFFF` 정규화 점수. 입력 동일 → 출력 동일.
- `model_version="mock-1.0"`, `elapsed_ms`는 `time.perf_counter` 측정.

### 5.3 Azure (`azure.py`) — 골격
- `httpx.AsyncClient` 재사용, `POST {scoring_uri}` + `Authorization: Bearer {key}`.
- **재시도**: 5xx/타임아웃 → 지수 백오프(`0.2 * 2**attempt`), 최대 `ml_max_retries`. 4xx → 즉시 `UpstreamError`.
- **타임아웃** → `MLTimeoutError(504)`, 재시도 소진 → `MLUnavailableError(502)`.
- **스키마 격리**: `_to_aml_payload`(현재 `{"input_data": inputs}`) / `_from_aml_response`. 실제 확정 시 **이 2함수만 수정**.
- scoring_uri/key 미설정 시 `ValueError`(설정 누락 조기 발견).

### 5.4 팩토리 / 수명주기 (`factory.py`)
- `ML_CLIENT==azure`면 지연 import 후 `AzureMLClient`, 아니면 `MockMLClient`.
- FastAPI `lifespan`에서 단일 생성 → `app.state.ml_client` → 의존성 주입(httpx 풀 재사용).
- gunicorn 멀티워커: **워커마다 lifespan 1회**(워커별 1클라이언트, 의도된 동작).

## 6. 횡단 관심사

| 관심사 | 구현 | 비고 |
|---|---|---|
| 인증 | `APIKeyHeader('X-API-Key')` + `secrets.compare_digest` | 상수시간 비교, 헬스 제외 |
| 검증 | Pydantic v2, `extra="forbid"`, `protected_namespaces=()` | `model_` 충돌 회피 |
| CORS | `CORSMiddleware`, `cors_origin_list` 비었으면 미적용 | credentials 시 `*` 금지 |
| Rate limit | `slowapi` `Limiter(key_func=client_ip)` | `client_ip`가 XFF 우선 파싱 |
| 요청 추적 | `RequestContextMiddleware` | X-Request-ID 생성/승계, 응답 헤더+로그 |
| 에러 표준화 | 전역 핸들러(AppError/422/HTTP/500) | `jsonable_encoder`로 detail 직렬화 |

## 7. 설정 (환경변수)

| 키 | 기본값 | 설명 |
|---|---|---|
| `API_KEY` | `dev-local-key` | X-API-Key 기대값 |
| `ML_CLIENT` | `mock` | `mock`\|`azure` |
| `AZURE_ML_SCORING_URI` | (없음) | 실제 연동 시 |
| `AZURE_ML_AUTH_PRI_KEY` / `AZURE_ML_AUTH_SEC_KEY` | (없음) | 엔드포인트 primary/secondary 키(시크릿). primary 우선·secondary 폴백 |
| `ML_TIMEOUT_CONNECT` / `ML_TIMEOUT_READ` | 5.0 / 30.0 | httpx 타임아웃(초) |
| `ML_MAX_RETRIES` | 2 | 재시도 횟수 |
| `CORS_ORIGINS` | `""` | 콤마 구분 허용 출처 |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | (없음) | App Insights 연결문자열(시크릿). 비우면 텔레메트리 no-op |
| `RATE_LIMIT_ENABLED` / `RATE_LIMIT` | true / `60/minute` | 레이트리밋 |

> 시크릿은 `.env`(로컬, 비커밋) 또는 App Service **Application Settings**(운영)로 주입.

## 8. 테스트 전략

- `ML_CLIENT=mock`로 전 구간 E2E. `httpx.ASGITransport`로 네트워크 없이 앱 직접 구동.
- 커버(11건): liveness/readiness, request_id 생성·승계, 401(누락/오키), 200(정상·결정성·dict 입력), 422(알수없는필드·필수누락).
- **주의**: ASGITransport는 lifespan을 실행하지 않음 → `conftest`에서 `app.state.ml_client` 수동 설정.
- 실행: `pytest` (`pytest.ini`: `asyncio_mode=auto`).

## 9. 배포 (App Service · Code) — ⚠️ 실행은 승인 필요

- **방식**: Oryx 빌드 기반 **Code 배포**(Docker 아님).
- **startup.sh**: `gunicorn -w 2 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 --timeout 600 app.main:app`.
- **포트**: 8000(Python Blessed Image·gunicorn 기본).
- **시크릿**: App Settings로 `API_KEY`, `AZURE_ML_*`, `CORS_ORIGINS`, `ML_CLIENT` 주입.
- **헬스체크 경로**: `/health`(무인증 → 플랫폼 프로브 통과).
- **대상 리소스**(지시서): RG `project-1st-team-3` / Plan `ASP-project1stteam3-8d76`(P0v3:1) / App `app-mlbackend-prod-kc-01` / Korea Central.

## 10. 비기능 요구 (NFR)

| 항목 | 목표/지침 |
|---|---|
| 가용성 | 헬스 프로브 + 워커 행 방지(타임아웃 계층화) |
| 확장성 | Stateless → 수평 확장(오토스케일) 안전 |
| 보안 | 시크릿 비커밋, 상수시간 키 비교, 내부 에러 비노출 |
| 추적성 | request_id 전파(헤더+로그) |
| 성능 | 워커 2(P0v3 보수값), 부하 측정 후 조정 |

## 11. 향후 과제 (Tech Debt)

- 실제 ML 연동(`azure.py` 변환 2함수) + 스키마 구체화.
- Redis 공유 스토리지 기반 전역 정밀 Rate limit(다중 인스턴스 정확성).
- 구조적 로깅(JSON) 고도화, 메트릭/트레이싱(App Insights) 연동.
- CI(테스트 자동화)·배포 파이프라인.

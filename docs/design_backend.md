# 백엔드 설계 문서 (검토용) — ML 연동 FastAPI 인프라

> 상태: **검토 대기**. 이 문서를 승인하면 자율 판단으로 구현에 착수합니다.
> 작성 근거: 공식 문서 팩트체크 완료 (하단 "근거" 참조). 본 개정판은 startup·Pydantic·Rate limit 항목을 재검증·수정함.
> 핵심 결정: ML 엔드포인트는 **추상화 레이어로 먼저 설계**, 실제 scoring URI·키·스키마는 나중에 주입.

---

## 0. 개정 이력

| 버전 | 변경 요지 |
|---|---|
| v1 | 최초 설계 |
| v2 (현재) | ① startup을 공식 권장(gunicorn+UvicornWorker)으로 확정 ② Pydantic v2 `model_` 네임스페이스 충돌 수정 ③ Rate limit의 멀티워커·프록시 한계 명시 ④ Mock을 "내부 스텁"으로 명확화(별도 Mock API 아님) ⑤ `gunicorn` 의존성 추가 ⑥ request_id·health 예외 처리 보강 |

---

## 1. 설계 목표와 범위

| 항목 | 결정 | 근거 |
|---|---|---|
| 게이트웨이 | FastAPI 내부 라우팅 + BFF 레이어 (APIM 미사용) | 지시서, 5일·소규모에 적정 |
| 인증 | API Key 헤더 (`X-API-Key`) | 사용자 확정 |
| ML 연동 | 추상화 레이어(인터페이스) + Mock 스텁 우선, 실제 구현 나중 주입 | 사용자 확정 |
| 배포 | Azure App Service **Code 방식** (Docker 아님) | 사용자 확정 |
| 런타임 | Python 3.14 (App Service Linux 정식 지원) | 공식 문서 확인 |
| 실행 서버 | **gunicorn + UvicornWorker** (포트 8000) | 공식 권장(아래 §10) |

**비범위(이번 제외):** Easy Auth/GitHub 로그인, APIM, DB, 사용자 세션, 별도 Mock 서비스/API.

---

## 2. 아키텍처 개요

```
                ┌─────────────────────────────────────────────┐
 클라이언트 ──▶ │  FastAPI (App Service, gunicorn+UvicornWorker)│
  X-API-Key     │                                              │
                │  [미들웨어]  RequestID → CORS → RateLimit     │
                │       │       → 요청로깅                      │
                │  [의존성]   verify_api_key (X-API-Key 검증)  │
                │       │      (health 경로는 인증·RateLimit 제외)│
                │  [라우터]   /health   /api/v1/predict        │
                │       │                                      │
                │  [서비스]   PredictionService (BFF 로직)     │
                │       │                                      │
                │  [추상화]   MLClient (인터페이스, ABC)        │
                │       ├── MockMLClient   (내부 스텁)          │
                │       └── AzureMLClient  (실제, 나중 활성화)  │
                └───────┼──────────────────────────────────────┘
                        ▼
                Azure ML Managed Online Endpoint
                POST {scoring_uri}  Authorization: Bearer {key}
```

> 미들웨어 순서 주의: FastAPI는 **나중에 추가한 미들웨어가 바깥(먼저 실행)**. RequestID를 가장 바깥에 둬 모든 로그·에러에 id가 붙도록 등록 순서를 역으로 구성.

**계층 책임 분리 (핵심):**
- **라우터**: HTTP 입출력·검증만. 비즈니스 로직 없음.
- **서비스(BFF)**: 요청 가공 → MLClient 호출 → 응답 가공. 프론트 친화적 형태로 재구성.
- **MLClient 추상화**: ML 호출의 *유일한* 접점. 구현체를 환경변수로 스위칭(`ML_CLIENT=mock|azure`).
  → 실제 엔드포인트 정보가 없어도 전체 파이프라인을 완성·테스트 가능. 정보 확보 시 `AzureMLClient`만 채우면 됨.

---

## 3. 프로젝트 구조 (제안)

```
azure-app-backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 앱 생성, lifespan, 미들웨어·라우터·예외핸들러 등록
│   ├── config.py               # pydantic-settings 기반 설정 (.env 로드)
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py             # verify_api_key, get_ml_client 등 의존성
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── health.py       # GET /health(liveness), /health/ready(readiness)
│   │       └── predict.py      # POST /api/v1/predict
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── prediction.py       # PredictRequest / PredictResponse
│   │   └── errors.py           # 표준 에러 응답 스키마
│   ├── services/
│   │   ├── __init__.py
│   │   └── prediction.py       # PredictionService (BFF)
│   ├── ml/
│   │   ├── __init__.py
│   │   ├── base.py             # MLClient(ABC) — 인터페이스 정의
│   │   ├── mock.py             # MockMLClient (내부 스텁, ~20줄)
│   │   ├── azure.py            # AzureMLClient (골격, 나중에 채움)
│   │   └── factory.py          # 환경변수로 구현체 선택
│   ├── core/
│   │   ├── __init__.py
│   │   ├── errors.py           # 커스텀 예외(AppError 계층)
│   │   ├── middleware.py       # RequestID·요청로깅 미들웨어
│   │   └── exception_handlers.py  # 전역 예외 핸들러
│   └── (logging 설정은 config/core에 통합)
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_health.py
│   ├── test_predict.py         # MockMLClient로 E2E
│   └── test_auth.py
├── docs/
│   ├── project_design.md       # 지시서(입력)
│   └── design_backend.md       # 본 설계 문서
├── .env                        # 시크릿 (커밋 금지)
├── .env.example                # 키 목록 템플릿 (커밋)
├── .gitignore
├── requirements.txt            # 런타임 의존성
├── requirements-dev.txt        # 테스트 등 개발 의존성
├── startup.sh                  # App Service 시작 명령 (버전관리 대상)
└── README.md
```

> 기존 루트 `main.py`는 `app/main.py`로 이전. App Service startup은 `app.main:app`을 가리킴.

---

## 4. ML 추상화 레이어 (핵심 설계)

### 4.1 인터페이스 (`app/ml/base.py`)

```python
from abc import ABC, abstractmethod
from app.schemas.prediction import PredictRequest, PredictResponse

class MLClient(ABC):
    @abstractmethod
    async def predict(self, request: PredictRequest) -> PredictResponse: ...

    @abstractmethod
    async def health(self) -> bool: ...   # 엔드포인트 도달 가능 여부

    async def aclose(self) -> None:       # 리소스 정리(기본 no-op)
        return None
```

### 4.2 Mock 구현 (`app/ml/mock.py`) — **내부 스텁, 오버스펙 아님**
- `MLClient`를 구현한 **수십 줄짜리 인프로세스 클래스**일 뿐, 별도 Mock 서버/Mock API가 아님.
- 입력을 받아 **결정적(deterministic) 가짜 예측** 반환(예: 입력 길이/해시 기반) → 테스트 재현성 확보.
- 목적은 단 하나: 실제 엔드포인트 없이 라우팅·검증·인증·에러·테스트 전 구간을 구동.
- (사용자 메모 반영) Mock "API 설계"는 본 프로젝트 범위에서 오버스펙으로 보고 **만들지 않음**. 필요해지면 별도 검토.

### 4.3 실제 구현 (`app/ml/azure.py`) — 골격만, 나중에 활성화
- `httpx.AsyncClient`로 `POST {AZURE_ML_SCORING_URI}`.
- 헤더: `Authorization: Bearer {AZURE_ML_KEY}`, `Content-Type: application/json` (공식 규약 확인됨).
  - authMode=key가 기본. AMLToken/AADToken은 향후 확장 지점으로만 표시(키는 만료 없음, 토큰은 만료 → 갱신 로직 필요).
- 타임아웃·재시도(지수 백오프, 최대 2회, 멱등 가정)·상태코드 매핑(5xx/타임아웃 → 502, 4xx → 그대로 전달).
- httpx 클라이언트 타임아웃은 gunicorn `--timeout`(기본 600s)보다 **작게** 설정(예: connect 5s / read 30s)해 워커 행 방지.
- **입출력 스키마 변환 지점**을 명시적 함수(`_to_aml_payload`, `_from_aml_response`)로 격리
  → 실제 엔드포인트 입출력 형태가 확정되면 이 두 함수만 수정.

### 4.4 팩토리 / 수명주기 (`app/ml/factory.py`)
- `settings.ml_client == "mock" | "azure"` 로 구현체 선택.
- FastAPI `lifespan`에서 단일 인스턴스 생성 → `app.state.ml_client`에 보관 → 의존성(`get_ml_client`)으로 주입(httpx 커넥션 풀 재사용).
- gunicorn 멀티워커에서는 **워커마다 lifespan이 1회씩** 실행 → 워커별 1개 클라이언트(정상, 의도된 동작).

---

## 5. 데이터 유효성 검사 (Pydantic v2)

`PredictRequest` / `PredictResponse`는 **추상 인터페이스 형태**로 먼저 정의(실제 스키마 확정 전 가정):

```python
from typing import Any
from pydantic import BaseModel, ConfigDict

class PredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")     # 알 수 없는 필드 거부
    inputs: list[float] | dict[str, Any]           # 실제 스키마 확정 시 구체화

class PredictResponse(BaseModel):
    # 'model_'로 시작하는 필드는 Pydantic v2 보호 네임스페이스와 충돌 → 경고 발생.
    # 해결: protected_namespaces=() 로 해제 (또는 필드명을 model_ 비접두로 변경).
    model_config = ConfigDict(protected_namespaces=())
    predictions: list[Any]
    model_version: str | None = None
    elapsed_ms: float
```

- **(수정 사항)** v1 초안의 `model_version`은 Pydantic v2에서 `Field "model_version" has conflict with protected namespace "model_"` 경고를 유발. 위와 같이 `protected_namespaces=()`로 명시 해제.
- 실제 ML 입출력 확정 시 이 스키마와 `AzureMLClient` 변환 함수만 갱신 (라우터·서비스 불변).

---

## 6. 인증 / CORS / Rate Limiting

| 기능 | 방식 | 비고 |
|---|---|---|
| 인증 | `fastapi.security.APIKeyHeader('X-API-Key')` 의존성 ↔ `settings.api_key` 를 `secrets.compare_digest`로 상수시간 비교 | OpenAPI(Swagger)에 자물쇠 표시. `/health*`는 제외 |
| CORS | `CORSMiddleware`, 허용 출처는 `.env`의 `CORS_ORIGINS`(콤마구분) | 기본 빈 목록(명시 필요). `allow_credentials=True` 시 `*` 금지 |
| Rate limit | `slowapi`(IP 기준, 예: 60 req/min) | **한계 있음 — 아래 참조**. `/health*` 제외 |

**Rate limiting 정직한 한계 (팩트):**
- slowapi 기본 저장소는 **인메모리** → 카운터가 ① gunicorn `-w 2` **워커별**로, 그리고 ② **인스턴스별**로 분리됨. 실효 한도 ≈ 설정값 × 워커수 × 인스턴스수.
- **⚠️ 오토스케일 주의**: 본 플랜은 P0v3(Premium v3)로 **오토스케일링(다중 인스턴스 scale-out)을 전제**로 선정·유지 확정됨. 인스턴스가 늘면 인메모리 카운터 분리가 심화되어 IP 기준 제한이 더 부정확해진다.
- App Service는 리버스 프록시 뒤 → 실제 클라이언트 IP는 `request.client.host`가 아니라 **`X-Forwarded-For`** 헤더에 있음. 정확한 IP 기준 제한을 하려면 `X-Forwarded-For` 파싱이 필요.
- 정밀/전역 제한이 필요하면 **Redis 등 공유 스토리지**(`limits` 백엔드)로 교체해야 함(인스턴스 간 카운터 공유). 단 본 프로젝트(비영리, 5일)에선 **근사적 보호로 충분** → 인메모리 + XFF 파싱으로 시작, Redis는 향후 과제(비범위).
- 설계 원칙: 오토스케일 전제이므로 **세션·캐시 등 in-memory 상태에 의존하지 않는 stateless 구조**를 유지한다.

> 결론: Rate limiting은 **도입 권장하되 "근사 보호" 성격임을 문서화**. 생략도 선택 가능(검토 의견 요청).

---

## 7. 에러 핸들링 표준화

**커스텀 예외 계층** (`app/core/errors.py`): `AppError(code, message, http_status)` → `MLUnavailableError`, `MLTimeoutError`, `UpstreamError` 등.

**전역 핸들러**가 모두 동일 포맷으로 변환:

```json
{
  "error": {
    "code": "ML_UNAVAILABLE",
    "message": "ML endpoint is temporarily unavailable.",
    "request_id": "uuid",
    "detail": null
  }
}
```

- `RequestValidationError`(422), `HTTPException`, 미처리 `Exception`(500), 커스텀 `AppError`(지정 status) 모두 통일 포맷.
- `request_id`는 RequestID 미들웨어에서 생성. **인바운드 `X-Request-ID` 헤더가 있으면 그대로 승계**, 없으면 새로 발급. 응답 헤더(`X-Request-ID`)와 구조적 로그에 동시 기록 → 추적성.
- 내부 예외 메시지·스택은 클라이언트에 노출하지 않음(로그에만). `detail`은 검증 오류 등 안전한 정보만.

---

## 8. 의존성 변경

**런타임 (`requirements.txt` 추가):**

| 패키지 | 용도 | 필수 |
|---|---|---|
| `pydantic-settings` | `.env` 설정 로드 | ✅ |
| `httpx` | ML 엔드포인트 async 호출 | ✅ |
| `gunicorn` | App Service 프로세스 매니저(UvicornWorker 구동) | ✅ (배포 필수) |
| `slowapi` | Rate limiting | 선택 |

> **(수정 사항)** v1에서 누락된 `gunicorn`을 추가. 공식 권장 startup이 gunicorn+UvicornWorker이므로 배포에 필수.

**개발 (`requirements-dev.txt` 분리):**

| 패키지 | 용도 |
|---|---|
| `pytest`, `pytest-asyncio` | 테스트 러너 |
| `httpx` | `ASGITransport` 기반 테스트 클라이언트(런타임과 공유) |

> 버전 핀: 설치 시점에 호환 버전을 확인해 **핀 고정**(기존 핀 셋: pydantic 2.13.4 / fastapi 0.137.2 / starlette 1.3.1 등과 호환 확인 후 확정). 추측 버전 기재 금지.

---

## 9. 로컬 테스트 전략

- `ML_CLIENT=mock`으로 전체 경로 E2E 테스트 (실제 엔드포인트 불필요).
- 커버: liveness/readiness / 정상 예측 / 잘못된 입력(422) / 인증 실패(401) / 알 수 없는 필드 거부(422) / ML 장애 시 502.
- 테스트 클라이언트는 `httpx.ASGITransport`로 앱 직접 구동(네트워크 불필요).
- 로컬 실행(개발): `uvicorn app.main:app --reload`. 테스트: `pytest`.

---

## 10. 배포 사전 설계 (⚠️ 실행은 승인 필수)

- **방식**: App Service **Code 배포** (Oryx 빌드). Docker 미사용.
- **실행 서버 (공식 권장, 확정):**
  ```bash
  # startup.sh (리포지토리에 보관 → 버전관리)
  gunicorn -w 2 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 --timeout 600 app.main:app
  ```
  - 포트 8000은 Python Blessed Image 기본 노출 포트. gunicorn도 기본 8000.
  - 워커 수 2는 P0v3(1 vCPU급) 기준 보수값. 부하 측정 후 조정.
  - 참고: 최신 App Service는 FastAPI 자동 감지로 startup 생략이 가능하나, **명시적 startup.sh를 두어 재현성·이식성 확보**(권장).
- **시크릿 주입**: `.env` 값들을 App Service **Application Settings**로 등록(키는 커밋 금지).
  - `API_KEY`, `AZURE_ML_SCORING_URI`, `AZURE_ML_KEY`, `CORS_ORIGINS`, `ML_CLIENT`
- **헬스체크**: App Service Health check 경로를 `/health`로 지정(인증·RateLimit 제외이므로 플랫폼 프로브 통과).
- 배포 명령·계획은 **별도 보고 후 대기** (이 문서 범위는 "사전 설계"까지).

---

## 11. 작업 순서 (승인 후)

1. 프로젝트 구조 생성 + `config.py` + `.env.example` + `startup.sh`
2. ML 추상화(base/mock/factory) + 스키마(Pydantic v2)
3. 라우터(health/predict) + 인증 의존성 + 서비스
4. 미들웨어(RequestID/CORS/RateLimit/로깅) + 전역 예외 핸들러
5. 테스트 작성·통과, 로컬 구동 검증
6. (별도 승인) `AzureMLClient` 실제 연결 + 배포 계획 보고

각 단계는 의미 단위 커밋.

---

## 근거 (팩트체크)

- **Python 3.14** Azure App Service for Linux 정식 지원 (2025-10-28 발표).
  https://techcommunity.microsoft.com/blog/appsonazureblog/python-3-14-is-now-available-on-azure-app-service-for-linux/4465404
- **ML 엔드포인트 호출**: `POST {scoring_uri}` + `Authorization: Bearer {key}` + `Content-Type: application/json`, authMode = key/AMLToken/AADToken.
  https://learn.microsoft.com/en-us/azure/machine-learning/how-to-authenticate-online-endpoint?view=azureml-api-2
- **권장 startup**: gunicorn + UvicornWorker, 포트 8000, 기본 timeout 600; `gunicorn`을 requirements에 포함해야 함. App Service의 FastAPI 자동 감지도 존재.
  https://learn.microsoft.com/en-us/azure/developer/python/configure-python-web-app-on-app-service
  https://learn.microsoft.com/en-us/azure/app-service/configure-language-python
  https://techcommunity.microsoft.com/blog/appsonazureblog/simplifying-fastapi-deployments-on-azure-app-service-for-linux/4520103

---

## 검토 요청 사항 (확인 필요)

1. **프로젝트 구조**: 루트 `main.py` → `app/main.py` 패키지 구조로 이전해도 될지? (권장: 이전)
2. **Rate limiting**: 인메모리+XFF로 "근사 보호" 도입 vs 생략? (권장: 도입)
3. **startup**: gunicorn+UvicornWorker로 확정 동의? (공식 권장 기반)
4. **dev 의존성**: `requirements-dev.txt` 분리 확정 동의? (권장: 분리)
5. 그 외 추가·수정 요청.
```

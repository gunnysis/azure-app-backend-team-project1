# Azure 인프라 정보 — ML 엔드포인트 & App Service 백엔드

> **수집일:** 2026-06-23 (Azure 포털 기준, **서비스용 `final-endpoint`**(스펙 상향 재생성)으로 갱신)
> **상태:** ✅ **서비스용(운영) 엔드포인트** 배포 완료(Healthy) — REST/Swagger URI 생성됨(§3).
> ✅ **전환 완료(2026-06-23)**: App Settings(URI·primary/secondary 키)를 `final-endpoint`(`361d14db…`)로 **재주입 + E2E 검증 통과**(`/health` 200, `/api/v1/predict` 200·`predictions` 반환). 구 `test4`(`7924e88e…`)·`final-version`(`517bf38a…`)은 재생성으로 삭제됨.
> ⚠️ **클라이언트 주의**: 피처명·타입 변경(`avg_temp`→`avg_temperature`, int64→double, §5.1) — 클라이언트 페이로드 키 수정 필요.
> **연계 문서:** [`../achieve/design_backend.md`](../achieve/design_backend.md) §4 (ML 추상화), §10 (배포)

---

## 1. Azure Machine Learning
| 항목 | 값 | 비고 |
|---|---|---|
| Resource group | `project-1st-team-3` | |
| Location | Korea Central | |
| Workspace | `team_3_ML` | |
| Subscription | `대한상공회의소` |  |
| Storage | `team3ml0750694230` |  |
| Studio web URL | `https://ml.azure.com?tid=f2d17c51-f5c8-4e25-a029-7fee401686c2&wsid=/subscriptions/b5a82513-0077-4885-a2d3-6aa00c3cac5b/resourcegroups/project-1st-team-3/providers/Microsoft.MachineLearningServices/workspaces/team_3_ML` | |
| Container Registry | `b34e5784fa234f3a9b46fef336d72615` |  |
| Key Vault | `team3ml5167553080` | |
| Application Insights | `team3ml0984223413` |  |
| Provisioning State | `Succeeded` |  |
| MLflow tracking URI | `azureml://koreacentral.api.azureml.ms/mlflow/v1.0/subscriptions/b5a82513-0077-4885-a2d3-6aa00c3cac5b/resourceGroups/project-1st-team-3/providers/Microsoft.MachineLearningServices/workspaces/team_3_ML` |  |

## 2. Azure Static Web Apps
| 항목 | 값 | 비고 |
|---|---|---|
| Location | East Asia | |
| instance 플랜 | `Standard` | |
| Deployment name | Microsoft.Web-StaticApp-Portal-3b3c4a0e-9782 | |
| Subscription | `대한상공회의소` |  |
| Resource group | `project-1st-team-3` | |
| Start time | 2026-06-23 15:09:00 | |
| Correlation ID | `f5801032-0a4a-45b9-b5e1-a9cf4af46cb2` |  |

## 3. Azure ML 엔드포인트

| 항목 | 값 | 비고 |
|---|---|---|
| Service ID | `final-endpoint` | |
| Description | 최종 | |
| **Deployment state** | **Healthy** |  |
| **Compute type** | **Container instance (ACI)** | classic **Designer** 실시간 웹서비스 (§5 분석) |
| Model ID | `amlstudio-final-endpoint:1` | `amlstudio-` 접두사 → AML Studio **Designer** 산출물 |
| Created by | 예찬 김 | |
| Created on | 2026-06-23 13:43 | |
| Last updated on | 2026-06-23 13:43 | |
| **REST endpoint** | `http://361d14db-fdac-4c50-84c2-688c34e95d04.koreacentral.azurecontainer.io/score` |  ⚠️ **http(평문)** — 키 평문 전송 |
| Key-based authentication enabled | `true` |  |
| **Swagger URI** | `http://361d14db-fdac-4c50-84c2-688c34e95d04.koreacentral.azurecontainer.io/swagger.json` |  |
| Image ID | `--` | |
| CPU | 2 vCPU |  |
| Memory | 1 GB |  |
| Application Insights | `false` | 비활성 (운영 모니터링 시 활성 검토) |
| Created by job |  |  |
| Asset ID |  |   |
---

## 4. App Service 백엔드

| 항목 | 값 |
|---|---|
| Subscription ID | `b5a82513-0077-4885-a2d3-6aa00c3cac5b` |
| Resource group | `project-1st-team-3` |
| Product | Web App |
| App Service Plan | `ASP-project1stteam3-8d76` (**P0v3**, 인스턴스 1) |
| App 이름 | `app-mlbackend-prod-kc-01` |
| 도메인 | `app-mlbackend-prod-kc-01-h4a6byekfzhkcday.koreacentral-01.azurewebsites.net` |
| 리전 | Korea Central |

> P0v3(Premium v3)는 **오토스케일 전제** → 백엔드는 stateless 유지(인메모리 상태 의존 금지).
> 자세한 근거: `design_backend.md` §6, 메모 `appservice-plan-premiumv3-autoscale`.

---

## 5. 점검 분석 — 설계와의 정합성

엔드포인트가 **Healthy**가 되어 REST/Swagger URI가 채워졌고, swagger 로 입출력 계약을 **실측 확정**했다.

### 🟢 해소됨 (이전 차단 이슈)
1. **배포 완료** — Deployment state `Healthy`, REST endpoint 생성됨 → **호출 가능**.
2. **입출력 스키마 확정** — Swagger 로 계약 실측(§5.1). 더 이상 추정 아님.

### 🟡 코드 정합화 (완료) 및 잔여 주의
3. **Compute type = `Container instance`(ACI), classic Designer 실시간 웹서비스.**
   실측 계약은 `{"Inputs":{"input1":[...]},"GlobalParameters":{}}` → `{"Results":{"WebServiceOutput0":[...]}}`
   형식으로, 당초 `azure.py`의 `{"input_data":...}`/`"predictions"` 가정과 **불일치(실버그)**였다.
   → **`app/ml/azure.py`의 변환 2함수·`app/schemas/prediction.py`·`mock.py`·테스트를 실계약으로 수정 완료**
   (설계상 격리 지점이라 라우터·서비스 계층 불변). 상세: [`../plans/design_ml_endpoint.md`](../plans/design_ml_endpoint.md) §8.
   **신규 `final-endpoint`도 동일 envelope·동일 계약**(swagger 실측, final-version과 100% 일치) → 변환 2함수·스키마 **코드 변경 불필요**(피처 비의존). 단 test4 대비 **피처명/타입은 변경**(§5.1).
4. **http(평문) 엔드포인트** — `Authorization: Bearer {key}`가 평문 전송됨. 테스트용으론 수용,
   **운영 전환 시 HTTPS 경로(AKS/관리형 엔드포인트)로 이전 권장**.

### 🟢 정상 / 참고
5. **Key-based auth 활성** → 설계의 키 주입 방식과 합치(`Bearer` 헤더). 키는 엔드포인트 단위 **primary/secondary**(`AZURE_ML_AUTH_PRI_KEY`/`AZURE_ML_AUTH_SEC_KEY`).
6. **CPU 2 vCPU / 1 GB** → 스펙 상향 재생성(구 test4/final-version은 0.1vCPU/0.5GB). 동시성 여유 확보, 단 ACI 특성상 콜드스타트 지연은 잔존.
7. **Application Insights 비활성** → 엔드포인트 측 추적 불가. 백엔드 자체 구조적 로그(`request_id`)로 보완.

### 5.1 실측 입출력 계약 (`final-endpoint`/swagger.json, 2026-06-23 실측)

> ⚠️ **test4 대비 변경점**: `avg_temp`→**`avg_temperature`**(개명), `prev_year_usage`·`current_usage` **int64→double**. 클라이언트 페이로드 키를 `avg_temperature`로 교체할 것. (`final-version`→`final-endpoint` 재생성 후 계약 동일 — 변경 없음.)

**요청 본문** (`POST /score`, `Authorization: Bearer {key}`):
```json
{"Inputs": {"input1": [
  {"prev_year_usage": 76, "avg_temperature": -0.46, "avg_humidity": 66.55, "total_rainfall": 21.1,
   "current_usage": 53, "thi": 36.1076813, "month_sin": 0.5, "month_cos": 0.8660254037844387}
]}, "GlobalParameters": {}}
```
**응답 본문:**
```json
{"Results": {"WebServiceOutput0": [
  {"prev_year_usage": 76, "...": "...(입력 피처 에코)", "Scored Labels": 61.2}
]}}
```
| 피처(필수 8개) | 타입 |
|---|---|
| prev_year_usage / current_usage | number (double) — *test4는 int64였음* |
| avg_temperature / avg_humidity / total_rainfall / thi / month_sin / month_cos | number (double) |
| **`Scored Labels`** (출력) | number (double) — 예측값 |

> 헬스 경로: `GET /` → `"Healthy"` (Bearer 필요).

---

## 6. 백엔드 연동 매핑 (App Service Application Settings)

배포 완료 후, 아래 값을 **App Service → Application Settings**에 주입(`.env` 커밋 금지):

| 설정 키 | 채울 값 (출처) | 현재 (2026-06-23 실측) |
|---|---|---|
| `ML_CLIENT` | `azure` (실연동 시) | ✅ `azure` (App Settings) |
| `AZURE_ML_SCORING_URI` | **`http://361d14db-…azurecontainer.io/score`** (`final-endpoint` REST endpoint) | ✅ **재주입 완료**(final-endpoint) |
| `AZURE_ML_AUTH_PRI_KEY`, `AZURE_ML_AUTH_SEC_KEY` | `final-endpoint` **인증 키** (포털 "Consume" 탭) | ✅ **재주입 완료**(미커밋, primary≠secondary 32자) |
| `API_KEY` | 백엔드 X-API-Key 기대값(강한 랜덤) | ✅ 주입(미커밋) |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | 기존 App Insights `team3ml0984223413` 연결문자열(재사용) | ✅ 주입(미커밋) |
| `CORS_ORIGINS` | 프론트 SWA origin(`https://thankful-desert-0cdb08500.7.azurestaticapps.net`) | ✅ **설정 완료**(2026-06-23) — 빈 값이라 CORS 미들웨어 미적용 상태였음 |

> ✅ **현 운영 상태(2026-06-23 전환 완료)**: App Settings를 `final-endpoint`(361d14db) URI + 신규 primary/secondary 키로 **재주입** 완료, 앱 재시작 후 **E2E 검증 통과**(`/health` 200, `/api/v1/predict` 200·`predictions` 반환·약 80ms). 구 `test4`(7924e88e)·`final-version`(517bf38a)은 재생성으로 삭제됨.
>
> ✅ **CORS 활성화(2026-06-23)**: SWA(`app-frontend-prod-kc-02`)에 linked-backend 가 없어(`az staticwebapp backends show`→`[]`) 프론트가 백엔드를 **브라우저 직접(cross-origin) 호출** → `CORS_ORIGINS` 가 비어 프리플라이트가 차단되던 상태. SWA origin 을 주입해 해결. 라이브 검증: `OPTIONS /api/v1/predict` → **200 + `Access-Control-Allow-Origin`**, 실제 `POST` 응답에도 ACAO 헤더 확인.

---

## 7. 후속 액션 (TODO)

- [x] 엔드포인트 배포 완료 → state `Healthy` 확인
- [x] **Swagger URI**로 실제 입출력 스키마 확보(§5.1)

> 아래 `[x]`는 **구 `test4` 기준** 이력. **신규 서비스용 `final-endpoint` 전환 작업은 미완** — 별도 항목으로 추적:
- [x] **App Settings 재주입**(2026-06-23) — `AZURE_ML_SCORING_URI`=`final-endpoint`(361d14db) URI + 신규 primary/secondary 키로 교체(App Settings로만 주입, 미커밋)
- [x] **E2E 재검증**(2026-06-23) — 앱 재시작 후 `/health` 200, `/api/v1/predict` 200 + `predictions` 반환 확인
- [x] **피처 개명 전파**(2026-06-23) — `avg_temp`→`avg_temperature`: `deploy.sh` 스모크·`app/ml/comsume.py`·테스트 2종·설계문서 정정. **근본 재발방지**: 샘플 행을 `app/schemas/prediction.py::EXAMPLE_INPUT_ROW` **단일 진실원**으로 통합(Swagger 예시·테스트·스모크 공유) + 회귀 테스트 2종 추가. `comsume.py`의 죽은 test4 URL 기본값 제거(`.env` URI 필수화). (PRD.md/TRD.md엔 `avg_temp` 리터럴 없음 — 단 "test4 swagger" 표현은 잔존, 비기능적이라 보류.)
- [x] **구 엔드포인트 정리** — `test4`·`final-version`은 재생성으로 **이미 삭제 확인**(2026-06-23, DNS 실패 실측) → 추가 정리 불필요
- [x] 실계약으로 `azure.py` 변환 2함수·`prediction.py`·`mock.py`·테스트 수정 (pytest green)
- [x] **인증 키 확보** → Consume 탭 기반으로 `.env` 에 `AZURE_ML_AUTH_PRI_KEY`/`AZURE_ML_AUTH_SEC_KEY` 저장(미커밋). (워크스페이스 단일 키는 없음 — 엔드포인트 단위 primary/secondary 키.)
- [x] `app/ml/comsume.py` 스모크 + `AzureMLClient` E2E 라이브 검증 성공
- [x] **운영 배포**: App Service에 키/URI·`ML_CLIENT=azure` App Settings 주입 + `deploy.sh`(OneDeploy) → `/health`·`/api/v1/predict` 200
- [x] **Application Insights 활성** + 알림/가용성 테스트 구성(§8)
- [x] **OTel 405→500 버그 수정·배포(2026-06-23)** — `opentelemetry-instrumentation-fastapi` 0.61b0 의 `_get_route_details` 가 `Match.PARTIAL`(메서드 불일치=405) 분기에서 `route.path` 를 try/except 없이 접근 → `include_router(prefix=…)` 의 `_IncludedRouter`(`.path` 없음)에서 `AttributeError` → 요청이 **500** 으로 떨어짐. **App Insights 활성 운영에서만 발현**(평시 pytest는 계측 미적용이라 못 잡음). 모든 405·CORS preflight(OPTIONS)·일부 헬스 프로브가 500 오염. **수정**: `app/observability.py` 에 멱등 가드(`_install_otel_partial_match_guard`)로 모듈 전역 span-details 함수 방어 래핑(계측 전 1회) + 회귀 테스트 2종. 라이브 검증: GET/POST 메서드 불일치 → **405**(이전 500).
- [x] **CORS 설정·배포(2026-06-23)** — SWA cross-origin 직접 호출용 `CORS_ORIGINS` 주입(§6). 프리플라이트 200 + ACAO 헤더 라이브 검증.
- [x] **Backend↔ML HTTPS 전환 — 보류(Reject) 결정(2026-06-23)**: 마감 임박(2일 전)으로 미적용. ML 호출은 평문(HTTP) 유지 + 보상통제(키 이중화·전송 최소화·App Insights 이상호출 알림)로 리스크 수용. 연구/제안서는 [`../plans/rejected/how_to_https_MLandBackend.md`](../plans/rejected/how_to_https_MLandBackend.md) 보존(재개 시 옵션 B=v2 관리형 엔드포인트 출발점, v1 EOL 2026-06-30 감안).

---

## 8. 모니터링 / 알림 (App Insights)

백엔드는 **Azure Monitor OpenTelemetry**로 계측되어 기존 App Insights `team3ml0984223413`(워크스페이스 기반)로 텔레메트리를 보낸다. requests / dependencies(httpx→ML ACI) / traces 수집 확인됨.

**가용성 테스트** (`webtest-mlbackend-health`, standard, 5분 주기, 3개 리전: 일본동부·동남아·동아시아)
- `GET /health` → 200 기대. 실패 시 아래 알림.

**알림 규칙** → 액션 그룹 `ag-mlbackend-alerts`(이메일: 등록 주소)
| 규칙 | 조건 | 심각도 |
|---|---|---|
| `alert-availability-low` | 가용성 < 90% (5분) | Sev1 |
| `alert-ml-dependency-failures` | ML 의존성 실패 count > 4 (5분) | Sev2 |
| `alert-server-exceptions` | 서버 예외 count > 0 (5분) | Sev2 |

> 알림 수신: 액션 그룹 이메일로 발송(최초 1회 Azure 구독 확인 메일 옵트인 필요).
> 포털: App Insights → Application Map / Failures / Availability 로 확인.
> 가용성 리전 추가는 포털에서 1클릭(현재 CLI 제약으로 3개 설정).

> ⚠️ **계측 자체의 함정(2026-06-23 해결, §7)**: OTel FastAPI 계측 0.61b0 의 `_get_route_details` 버그로 **모든 405·OPTIONS 프리플라이트가 500** 으로 떨어져, `alert-server-exceptions`(서버 예외>0)를 상시 트리거하고 Failures 를 오염시켰다. `app/observability.py` 가드로 수정. 텔레메트리 헬퍼는 요청을 깨선 안 된다는 원칙(span 이름 실패 시 메서드명 폴백)으로 재발방지.

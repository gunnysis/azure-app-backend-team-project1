# Azure 인프라 정보 — ML 엔드포인트 & App Service 백엔드

> **수집일:** 2026-06-22 (Azure 포털 기준, `test4` 엔드포인트로 갱신)
> **상태:** ⚠️ **테스트용 엔드포인트**(실제 모델/스키마 확정 전). 단, 배포는 **완료(Healthy)** — REST endpoint·Swagger URI 생성됨(아래 §1 참조).
> **연계 문서:** [`../design_backend.md`](../design_backend.md) §4 (ML 추상화), §10 (배포)

---

## 1. Azure ML 엔드포인트

| 항목 | 값 | 비고 |
|---|---|---|
| Service ID | `test4` | |
| Description | 정건님께 정말 드리고싶은 선물 그 4번째 | |
| **Deployment state** | **Healthy** | ✅ 배포 완료 — 호출 가능 |
| **Compute type** | **Container instance (ACI)** | classic **Designer** 실시간 웹서비스 (§3 분석) |
| Model ID | `amlstudio-test4:1` | `amlstudio-` 접두사 → AML Studio **Designer** 산출물 |
| Created by | 예찬 김 | |
| Created on | 2026-06-22 15:55 | |
| Last updated on | 2026-06-22 15:55 | |
| **REST endpoint** | `http://7924e88e-ebe7-44eb-8e63-1b49ea44aa93.koreacentral.azurecontainer.io/score` | ✅ 생성됨. ⚠️ **http(평문)** — 키 평문 전송 |
| **Swagger URI** | `http://7924e88e-…azurecontainer.io/swagger.json` | ✅ 입출력 스키마 확보(§3.1) |
| Image ID | `--` | |
| Key-based authentication | `true` | 키 기반 인증 활성 |
| CPU | 0.1 vCPU | 테스트용 최소 사양 |
| Memory | 0.5 GB | 테스트용 최소 사양 |
| Application Insights | `false` | 비활성 (운영 모니터링 시 활성 검토) |

---

## 2. App Service 백엔드

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

## 3. 점검 분석 — 설계와의 정합성

엔드포인트가 **Healthy**가 되어 REST/Swagger URI가 채워졌고, swagger 로 입출력 계약을 **실측 확정**했다.

### 🟢 해소됨 (이전 차단 이슈)
1. **배포 완료** — Deployment state `Healthy`, REST endpoint 생성됨 → **호출 가능**.
2. **입출력 스키마 확정** — Swagger 로 계약 실측(§3.1). 더 이상 추정 아님.

### 🟡 코드 정합화 (완료) 및 잔여 주의
3. **Compute type = `Container instance`(ACI), classic Designer 실시간 웹서비스.**
   실측 계약은 `{"Inputs":{"input1":[...]},"GlobalParameters":{}}` → `{"Results":{"WebServiceOutput0":[...]}}`
   형식으로, 당초 `azure.py`의 `{"input_data":...}`/`"predictions"` 가정과 **불일치(실버그)**였다.
   → **`app/ml/azure.py`의 변환 2함수·`app/schemas/prediction.py`·`mock.py`·테스트를 실계약으로 수정 완료**
   (설계상 격리 지점이라 라우터·서비스 계층 불변). 상세: [`../plans/design_ml_endpoint.md`](../plans/design_ml_endpoint.md) §8.
4. **http(평문) 엔드포인트** — `Authorization: Bearer {key}`가 평문 전송됨. 테스트용으론 수용,
   **운영 전환 시 HTTPS 경로(AKS/관리형 엔드포인트)로 이전 권장**.

### 🟢 정상 / 참고
5. **Key-based auth 활성** → 설계의 키 주입 방식과 합치(`Bearer` 헤더). 키는 엔드포인트 단위 **primary/secondary**(`AZURE_ML_AUTH_PRI_KEY`/`AZURE_ML_AUTH_SEC_KEY`).
6. **CPU 0.1 / 0.5GB** → 테스트용 최소 사양. 동시성·콜드스타트 지연 한계 있음(부하 테스트 시 감안).
7. **Application Insights 비활성** → 엔드포인트 측 추적 불가. 백엔드 자체 구조적 로그(`request_id`)로 보완.

### 3.1 실측 입출력 계약 (swagger.json)

**요청 본문** (`POST /score`, `Authorization: Bearer {key}`):
```json
{"Inputs": {"input1": [
  {"prev_year_usage": 76, "avg_temp": -0.46, "avg_humidity": 66.55, "total_rainfall": 21.1,
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
| prev_year_usage / current_usage | integer (int64) |
| avg_temp / avg_humidity / total_rainfall / thi / month_sin / month_cos | number (double) |
| **`Scored Labels`** (출력) | number (double) — 예측값 |

> 헬스 경로: `GET /` → `"Healthy"` (Bearer 필요).

---

## 4. 백엔드 연동 매핑 (App Service Application Settings)

배포 완료 후, 아래 값을 **App Service → Application Settings**에 주입(`.env` 커밋 금지):

| 설정 키 | 채울 값 (출처) | 현재 |
|---|---|---|
| `ML_CLIENT` | `azure` (실연동 시) | `mock` |
| `AZURE_ML_SCORING_URI` | `http://7924e88e-…azurecontainer.io/score` (REST endpoint) | ✅ 확보 |
| `AZURE_ML_AUTH_PRI_KEY`, `AZURE_ML_AUTH_SEC_KEY` | 엔드포인트 **인증 키** (포털 "Consume" 탭) | (테스트용) ✅(미커밋) |

---

## 5. 후속 액션 (TODO)

- [x] 엔드포인트 배포 완료 → state `Healthy` 확인
- [x] **Swagger URI**로 실제 입출력 스키마 확보(§3.1)
- [x] 실계약으로 `azure.py` 변환 2함수·`prediction.py`·`mock.py`·테스트 수정 (pytest green)
- [x] **인증 키 확보** → Consume 탭 기반으로 `.env` 에 `AZURE_ML_AUTH_PRI_KEY`/`AZURE_ML_AUTH_SEC_KEY` 저장(미커밋). (워크스페이스 단일 키는 없음 — 엔드포인트 단위 primary/secondary 키.)
- [ ] `app/ml/comsume.py` 로 1건 스모크(`python -m app.ml.comsume`, `.env` 자동 로드) -> 직접 작업/디버깅/재발방지 작업 병행
- [ ] `ML_CLIENT=azure`로 전환 후 `/api/v1/predict` E2E (실연동은 **승인 후** 진행)
- [ ] (운영 전환 시) **HTTPS 경로 이전**, Application Insights 활성, CPU/Memory 사양 재검토

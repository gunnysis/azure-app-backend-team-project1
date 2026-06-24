# user_flow.md 점검·검토 보고서 (기획 대비 실제 구현)

> 문서 성격: 초기 기획 문서 [`user_flow.md`](user_flow.md)가 정의한 로직·프로세스·기능·인프라를 **실제 구현(백엔드 · 프론트엔드 · Azure ML 3축)** 과 대조 점검한 결과.
> 작성일: 2026-06-24 · 대상 커밋: `main`(2603ad9 기준) · 점검 방식: 코드 정독 + 계약 문서 교차검증(추측 배제).
> 관련 문서: [PRD](PRD.md) · [TRD](TRD.md) · [SPEC](SPEC.md) · 프론트 [`API_CONTRACT.md`](../../azure-app-frontend/API_CONTRACT.md)

---

## 0. 점검 범위 / 대상

| 축 | 경로 | 핵심 파일 |
|---|---|---|
| 백엔드(BFF/게이트웨이) | `azure-app-backend` | `app/api/v1/adapter.py`, `app/services/feature_builder.py`, `app/ml/azure.py`, `app/data/seoul_climate.py` |
| 프론트엔드(정적 SWA) | `azure-app-frontend` | `script.js`(`buildPayload`/`requestPrediction`/`normalizePredictionResponse`/`localMockPredict`/`calculateElectricBill`), `config.js` |
| ML | Azure ML Designer 실시간 엔드포인트(ACI classic) | `_to_aml_payload`/`_from_aml_response` (변환 격리 2함수) |

---

## 1. user_flow.md 원안 10단계 ↔ 실제 구현 매핑

| # | 원안(기획) | 실제 구현 위치 | 판정 |
|---|---|---|---|
| 1 | 프론트 입력 전송: **평수·에어컨 시간·구청코드·선택 월** | `buildPayload()` → `region/housing_type/household_size/has_aircon/aircon_hours_per_day/aircon_power_w/aircon_type` | ⚠️ **변경·축소** (아래 F1·F2) |
| 2 | 피처 복원: **평수/시간 → 가상 전년사용량** | `feature_builder.estimate_usage()` — `prev_year_usage=132 상수`, `current_usage=132+에어컨델타` | ⚠️ **변경** (평수 미사용, 상수 기반) |
| 3 | 날씨 매핑: 기온·습도·강수량·불쾌지수 | `seoul_climate.monthly_weather()` + `compute_thi()` | ✅ 구현(단, 평년값 — F8) |
| 4 | Azure ML JSON 페이로드 구성 | `azure._to_aml_payload()` → `{"Inputs":{"input1":[...]}}` | ✅ 일치 |
| 5 | REST 호출(Bearer Token) | `azure.predict()` — `Authorization: Bearer {key}` | ✅ 일치(단, 평문 HTTP — F6) |
| 6 | 모델 추론 | Azure ML Designer 엔드포인트 | ✅ |
| 7 | 예측 사용량(current_usage) 반환 | `_from_aml_response()` → `"Scored Labels"` 추출 | ⚠️ **개념 혼동**(F3) |
| 8 | 백엔드 사용량 수신 | `adapter.estimate()` `_coerce_score()` | ✅ |
| 9 | 최종 사용량 + **계산 금액** 패키징 | 백엔드는 `predicted_kwh`/`baseline_kwh`만, **금액은 프론트 계산** | 🔁 **설계 변경(의도)** |
| 10 | 프론트 그래프·요금 고지서 렌더 | `normalizePredictionResponse()` + `calculateElectricBill()` | ✅ |

**요약:** 4·5·6·8·10단계는 기획과 정합. 1·2·7은 기획과 갈라졌으나 **프로젝트 결정으로 모두 정리됨**(1 현재 월 고정 수용, 2·7 수용·확정, 9 의도적 변경). 입력 모델·ML 역할의 미결 제품 결정은 없음.

---

## 2. 발견사항 (프로젝트 결정 반영)

> **상태 라벨:** ✅ 수용·확정(조치 없음) · 📝 문서 정정(코드 무변경) · 🔧 구현 조치(설계 대상) · ⚠️ 수용된 리스크(기록·과금 발생 시 승인 게이트) · ❓ 결정 대기

### ✅ F1 — `month`(선택 월) 미입력 → 항상 "현재 월(KST)" 예측  *(수용·확정 — 월 선택 미도입)*
- **결정:** 월 선택 UI는 **추가하지 않음**. 예측은 항상 서버 현재 월(KST) 기준. `buildPayload()`는 `month` 미전송 유지, `adapter.estimate()`가 현재 월로 대체.
- **참고:** 백엔드 `EstimateRequest.month`는 optional로 남겨 둠(향후 필요 시 프론트만 추가하면 동작, 백엔드 무변경). 별도 제거는 불필요.

### ✅ F2 — `평수`·`구청코드` 입력 안 함  *(수용·확정)*
- **결정:** 마포·원룸·1인 고정 MVP 스코프. `prev_year_usage=132` 상수 유지. user_flow 원안의 "평수 기반 사용량 복원"은 도입하지 않음.

### 📝 F3 — ML 역할의 개념적 순환: `current_usage`는 모델 *입력*인데 "예측 사용량"으로 표기  *(아키텍처 수용 · 문서 정정)*
- **근거:** 모델 입력 8피처에 `current_usage`가 포함(`feature_builder.build_features`). 그 `current_usage`는 **에어컨 습관에서 백엔드가 추정한 값**(`132 + 에어컨델타`). 모델 출력은 별도의 `"Scored Labels"`(= `predicted_kwh`). user_flow 7단계는 "모델이 current_usage 반환"이라 적었으나, 실제 `current_usage`는 **반환값이 아니라 투입값**.
- **영향(2026-06-24 라이브 실측으로 정정):** 휴리스틱(`estimate_usage`)은 모델 *입력*(`current_usage`)을 결정하지만, **모델이 그 값을 크게 변형**한다 — 실측: `current_usage=224.74` 입력 → 라이브 `predicted_kwh ≈ 141`(6월)·`152`(7월), 약 **−32~37%**. 따라서 "ML은 작은 보정자, 예측의 대부분은 휴리스틱이 결정"이라던 **초기 서술은 반증됨**(모델이 실질적으로 수치를 재형성). 함의: 휴리스틱만 복제 가능한 **폴백(F4)은 라이브와 큰 차이**가 남는다(§6 운영 검증·F4 §10). **버그가 아니라 MVP 설계상 한계**(메모리 [estimate-adapter-weather-usage-are-estimates])지만, 보정폭이 크다는 사실은 정정 기록.

### ✅ F4 — 프론트 폴백(`localMockPredict`)이 라이브 경로와 수치 불일치  *(구현 완료 2026-06-24 — 푸시 대기. 설계·로그: [`plans/design_fallback_parity.md`](plans/design_fallback_parity.md))*
- **근거:** `feature_builder.py`는 타입별 전력(`fixed=760/inverter=560/unknown=650`)과 배수(`1.1/0.92/1.0`)를 반영. 반면 프론트 `localMockPredict()`는 `powerKw = hours>0 ? 0.65 : 0` **고정**으로, 사용자가 입력한 `aircon_power_w`·`aircon_type`을 **무시**. 일치하는 건 `base 132`·`30일`·`clamp 85~650`·`단시간 +8`뿐.
- **수치 예(인버터·6시간·전력 미입력):**
  - 백엔드(라이브): `6×30×0.56×0.92 = 92.7` → `132+92.7 ≈ 224.7 kWh`
  - 프론트(폴백): `6×30×0.65 = 117` → `132+117 = 249 kWh` (약 **+24kWh, +11% 괴리**)
- **영향:** 백엔드 장애로 폴백 발동 시 사용자에게 보이는 숫자가 평소(라이브)와 달라지고, **사용자는 폴백 여부를 화면상 구분 불가**(콘솔 경고 + `source=fallback`만). `feature_builder.py` 주석의 "프론트 localMockPredict와 정합" 표현은 **부분적으로만 사실**.

### ⚠️ F5 — 무키 `/estimate` 남용 → Azure ML 과금 리스크  *(수용된 리스크 · 완화는 과금 승인 게이트)*
- **근거:** `/api/v1/estimate`는 의도적으로 무키(`adapter.py` — 브라우저에 키를 둘 수 없음). 보호는 **CORS 출처 화이트리스트 + rate limit**뿐.
- **분석:** CORS는 **브라우저 한정** 보호 — `curl`/서버측 요청은 `Origin` 위조로 우회 가능(CORS는 응답 차단이지 요청 차단이 아님). rate limit은 인메모리·근사(F7)라 다중 인스턴스에서 정확도 낮음. → URL만 알면 **외부에서 Azure ML 추론을 반복 호출해 과금 유발** 가능.
- **결정:** 비영리·소규모 MVP에서 **수용된 리스크로 기록**. 완화(Redis 공유 rate limit, 경량 봇 방지, App Service 일일 호출 상한/알림)는 **필요 시 과금 발생 작업으로 승인 요청 후 진행**(요청→검토→승인→실행). 무키 직접 호출은 §3의 "과금 시 승인" 운영 가드 **밖**이므로, 비용 폭주가 실제 관측되면 그때 완화를 승인 안건으로 올린다.

### ⚠️ F6 — ML 엔드포인트 평문 HTTP → Bearer 키 평문 전송  *(현재 HTTP 유지 — 확정)*
- **결정:** ACI(Designer classic) 엔드포인트 http 평문 유지. 백엔드↔ML 구간 Bearer 키 평문 전송을 **수용된 리스크로 기록**. 키 노출 최소화(로그·커밋 금지)로 보완. HTTPS(Managed Online Endpoint) 전환은 본 프로젝트 범위 밖.

### ⚠️ F7 — 인메모리 rate limit, 오토스케일 다중 인스턴스에서 부정확  *(수용된 리스크)*
- **근거:** `slowapi` 인메모리 카운터(`ratelimit.py`), P0v3 오토스케일 전제(메모리·TRD D7/D9). 인스턴스 간 카운터 비공유.
- **영향:** 스케일아웃 시 실제 허용량이 `설정값 × 인스턴스 수`로 늘어 **근사 보호**. F5와 결합 시 남용 방어가 더 약해짐. 문서화된 한계.

### ✅ F8 — 기상은 실시간이 아닌 월별 기후평년값(1991–2020)  *(수용·확정)*
- **결정:** 단기간 프로젝트로 실시간 기상 대신 **고정 데이터(서울 108 월별 기후평년값 1991–2020)** 기반 유지. 실시간/해당연도 기상 고도화는 범위 밖.

### 🟩 정합·양호 항목
- **타임아웃 좌표(F-good):** 백엔드 ML 예산 `estimate_ml_deadline_s=6.0s` < 프론트 abort `8000ms`. 느린 ML도 백엔드가 6s에 504로 끊어 프론트가 8s 전에 graceful fallback. 좌표 유지 필수(메모리 [estimate-adapter-coordination-invariants]).
- **baseline 동봉:** 같은 ML 호출에 2행(사용자/에어컨OFF) 배치 → `predictions[1]`이 계절성 기준선. **추가 호출·과금 없음**.
- **요금식 단일 소스:** 백엔드는 `bill` 미제공, 프론트 `calculateElectricBill()` 단일 계산 → 요금식 이중화·드리프트 방지(설계 의도).
- **ML 추상화 격리:** 스키마 변경은 `_to_aml_payload`/`_from_aml_response` 2함수 + `.env`로 국소화. 라우터·서비스 불변.
- **에러 표준화·request_id·CORS 화이트리스트·상수시간 키 비교** 등 횡단 관심사 일괄 적용.

---

## 3. 인프라 점검 - Azure instance는 오토스케일리이 가능하고 필요시 비용 지불 가능. 과금 발생시 승인 후 작업 가능

| 구간 | 구성 | 점검 결과 |
|---|---|---|
| 프론트 | Azure Static Web Apps Standard, `main` 푸시 시 자동 배포(GitHub Actions) | ✅ CSP `connect-src`에 운영 백엔드만 허용, `config.js` 호스트 가드로 dev 오배포 방지. ⚠️ `main` 푸시=실배포(메모리 [frontend-push-triggers-swa-deploy]) → **승인 필수** |
| 백엔드 | App Service P0v3(Code 배포, Oryx), gunicorn 2 worker, stateless | ✅ 워커당 lifespan 1회·커넥션 풀 재사용. ⚠️ 인메모리 ratelimit 근사(F7). 재배포 수동 `deploy.sh`(메모리 [onedeploy-502-false-negative]) |
| ML | Azure ML Designer ACI classic, 엔드포인트 primary/secondary 키 | ⚠️ **http 평문(F6)**. health는 보수적으로 도달성만 보고(업스트림 ping 안 함 → 과금 회피) |

---

## 4. 설계 착수 전 처리할 항목

> 결정으로 닫힌 항목(F1·F2·F5·F6·F7·F8)은 제외. 아래만 설계 단계로 넘어가기 전 처리한다.

| 우선 | 항목 | 처리 | 비고 |
|---|---|---|---|
| P1 | **F4 폴백 정합** | `localMockPredict`에 타입별 전력·배수 반영(백엔드 상수 동일) 또는 주석을 "근사 폴백"으로 정정 | 유일한 코드 액션. 라이브/폴백 괴리 ≤ 수%. 프론트 `main` 수정=SWA 실배포 → 승인 후 |
| P2 | **문서 정본화(F3·F9)** | 본 검토 문서를 정본으로, `user_flow.md`는 **초기 기획안으로 동결(참고)**. F3 개념·F9 책임이전을 본 문서에 명시(완료) | user_flow 동기화 부담 제거 |

> **F9(설계 변경 명시):** 10단계의 "금액 패키징"은 백엔드→프론트로 책임 이전(요금식 단일 소스화)된 **의도된 변경**. 본 문서에 명시로 갈음.

---

## 5. 결론

- **파이프라인 골격(4·5·6·8·10)** 은 user_flow 기획대로 정상 동작하며, ML 추상화·에러표준화·타임아웃 좌표·요금식 단일화 등 설계 품질은 양호하다.
- **입력 모델·ML 역할의 기획 대비 차이는 프로젝트 결정으로 정리됨**: 평수·구청코드 미입력(F2 수용), `current_usage`=모델 입력·ML은 보정자(F3 수용·문서 정정), 금액은 프론트 단일 계산(F9). 모두 **마포·원룸·1인 MVP 스코프**에 따른 의도된 단순화이며, `user_flow.md`는 **초기 기획안으로 동결(참고)**, 본 검토 문서를 정본으로 둔다.
- **수용된 리스크(기록)**: 무키 엔드포인트 과금 노출(F5)·ML 평문 HTTP(F6)·인메모리 rate limit(F7)·평년값 기상(F8). 완화가 과금을 유발하면 **요청→검토→승인→실행** 게이트로 진행한다.
- **F1(월 선택)은 미도입으로 확정** — 예측은 항상 현재 월(KST) 기준. 제품 결정은 모두 닫혔고, **설계 착수 전 남은 것은 🔧F4(폴백 정합) 코드 액션 하나**. F4가 정리되면 구현 설계로 진입 가능하다.

---

## 6. 운영 검증 로그 (2026-06-24, 라이브 점검)

**배포·인프라 정상:**
- ✅ **SWA 배포**: F4 커밋 워크플로 `success`(1m11s). 라이브 `index.html`=`?v=20260624-fallback-parity`, `script.js`에 `airconMarginalKwh` 반영·구 `0.65` 고정 제거 확인.
- ✅ **백엔드 헬스**: `/health` 200, `/health/ready` `{ml:true}`. **CORS**: `/api/v1/estimate` preflight 200 + `Access-Control-Allow-Origin`=SWA 출처. **라이브 ML E2E**: 무키 POST → 200(`predicted_kwh` 반환).

**🟥 발견 A — 프로덕션 백엔드가 구버전(미배포 격차):**
- **증거(무과금 확정)**: 프로덕션 `/openapi.json`의 `EstimateResponse`에 **`baseline_kwh` 필드 없음**(로컬 main HEAD엔 존재). 응답에도 부재(null 아님).
- **의미**: 커밋 `2603ad9`(**계절성 baseline + `/estimate` 6s 총예산**)가 **프로덕션 미배포**. 운영 코드는 그 이전 버전.
- **영향**: ① **baseline 계절값 미전달** → 프론트가 `baseline_kwh` 없으면 **165 고정 폴백**(계절성 baseline 기능이 실제로는 미동작 — 메모리·`API_CONTRACT`의 "baseline 라이브" 서술과 불일치). ② **6s 총예산(`estimate_ml_deadline_s`) 미적용** → 타임아웃 좌표(백 6s < 프 8s) **프로덕션에서 미보장**(느린 ML+재시도가 프론트 8s abort를 선점할 수 있음 — 메모리 [estimate-adapter-coordination-invariants] 무효화).
- **근본 원인**: 백엔드는 **CI/CD 부재**(`.github/workflows` 없음) → main 커밋이 자동 배포 안 됨, 수동 `deploy.sh`만. `2603ad9`(2026-06-24, baseline+6s 동시 도입)가 **커밋만 되고 `deploy.sh` 미실행**. 반면 프론트는 push=자동배포(SWA CI). → **프론트(자동)·백엔드(수동) 비대칭**이 양쪽 걸친 기능에서 **계약 드리프트 창**을 만든다(구조적 원인).
- **조치(승인 필요)**: 백엔드 `deploy.sh` **재배포** = "실제 배포"라 **승인 필수**. 재배포 시 두 기능 모두 라이브화. (과금: App Service 기존 인스턴스라 추가 과금 없음, 단 배포 행위 자체는 승인 게이트.)
- **재발방지**: ① (즉시) 재배포 후 본 `/openapi.json`에 `baseline_kwh` 존재로 검증. ② (단기) **배포 후 스모크 체크리스트**에 "OpenAPI 계약 = main 일치" 1항 추가. ③ (근본) 백엔드 **CI 자동배포 도입**(TRD §11 기존 tech debt) — 프론트와 배포 모델을 정합시켜 비대칭 제거. ④ 프론트 `API_CONTRACT.md`·메모리의 "baseline 라이브" 서술은 **재배포 전까지 미달성** — 재배포로 해소하거나 서술 정정.

**🟧 발견 B — ML 출력 변형폭이 큼(F3 정정 근거):**
- 실측: `current_usage=224.74` 입력 → 라이브 `predicted_kwh ≈ 141~152`(약 −32~37%). 모델이 휴리스틱 추정치를 **실질적으로 낮춤**.
- **함의**: F4 폴백은 백엔드 추정식과 정확 일치(검증 완료)하나, **라이브(ML 출력)와는 큰 차이**가 남는다 — 이는 설계상 수용된 ML 델타([F3]·F4 §10)이며 폴백은 장애 시 graceful 표시값. 단 "수%"가 아니라 **수십%** 임을 정정 기록.

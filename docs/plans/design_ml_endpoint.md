# ML 엔드포인트 연동 설계 (현행) + 생성 설계 (참고) — v6

> ## ✅ 2026-06-22 갱신 — 엔드포인트는 **이미 존재**(ACI `test4`, Healthy)
> 팀(예찬 김)이 모델을 **Designer 실시간 웹서비스(ACI)로 배포 완료**했다. 따라서:
> - 본 문서가 다루던 **"엔드포인트를 새로 생성"하는 과제는 대부분 종료** — §4~7·§9~12(생성 절차/경로 선택/생성 승인)은
>   **참고·대안(향후 EOL 대응 재생성 시)** 으로 격하. 지금 실행할 필요 없음.
> - **유효·핵심**: §2(입출력 계약, **swagger 로 실측 정정**)와 §8(백엔드 연동, **실계약으로 구현 완료**).
> - 실측 엔드포인트 정보·계약 원본: [`../azure/ML_info.md`](../azure/ML_info.md) §1·§3.1.
> - v2 강제 이전 분석([`rejected/design_ml_endpoint_v2.md`](rejected/design_ml_endpoint_v2.md))은 채택되지 않아 **반려(rejected)**.
>
> 작성 근거: `az ml`/`az vm` CLI 실측 + 모델 아티팩트 다운로드 + **배포된 엔드포인트 swagger.json 실측** + 공식 문서 팩트체크(§11).

---

## 문서 상태 · 읽는 법 (v5)

- **상태**: `holding/` → **`plans/`(active)** 승격. v2 강제이전 문서는 `rejected/` 로 이동.
- **현행(active) — 지금 유효**: **§0**(요약) · **§2**(실측 계약) · **§8**(백엔드 연동·구현 완료) · **§10**(검증) · **§12**(남은 결정).
- **참고/보류(parked) — 엔드포인트가 이미 존재해 실행 불필요, 재생성 검토 시만 참조**: §1·§3(R1~R6)·§4~7·§9·§11.

| 한눈에 | 상태 |
|---|---|
| 엔드포인트 | ACI `test4` **Healthy**, REST/Swagger 생성됨 |
| 입출력 계약 | **swagger 실측 확정** (§2·§3.1) |
| 백엔드 코드 | 실계약 반영 **구현 완료**, pytest 13 passed |
| 남은 일 | (키 `.env` 저장됨) 스모크 → `ML_CLIENT=azure` E2E (**승인 후**) |

## 개정 이력
| 버전 | 변경 요지 |
|---|---|
| v1 | 최초 설계(엔드포인트/배포 YAML, CLI 절차, 백엔드 연동 초안) |
| v2 | ① 쿼터 **실측**(DSv2 0/50)으로 R1 완화 ② `AZUREML_MODEL_DIR` 마운트 동작 공식 확인 → R4 근본 분석 ③ **Designer 클래식의 v2 호환성**을 최상위 리스크로 격상(공식 문서가 api-1) ④ VM SKU 지원·프로브 주의 팩트체크 ⑤ 비용 추정치 추가 ⑥ **백엔드 스키마 불일치(실버그) 발견** 및 근본 수정안 ⑦ 로컬 사전검증(`--local`) 옵션과 Docker 전제 ⑧ CLI vs Studio 의사결정 매트릭스 |
| v3 | **전제 변경 반영**: `electricity_model`은 **테스트용·교체 가능**. ① 모델 가변성 영향도 분석 신설(§0.1) ② (※v4에서 철회) 최종 모델 MLflow 등록 권장 ③ §8 권장을 **제네릭 우선**으로 조정 ④ "리허설 1회 후 삭제 vs 최종 모델 대기" 추가 |
| v4 | **"Designer 사용 기반 확정" 반영(핵심 정정)**: ① **클래식 Designer(v1) 모델은 v2 관리형 온라인 엔드포인트를 공식 미지원** — 공식 배포 대상은 **ACI/AKS**(팩트체크 §11) ② v3의 MLflow 권장 **철회**(Designer 확정이므로 무효) ③ R0를 "빌드 리스크"→**"공식 미지원 경로"**로 정정·격상 ④ ~~SDK/CLI v1 지원 종료 2026-06-30~~(v5에서 정정) 임박 사실 추가 ⑤ 배포 경로 의사결정 재구성(§0.1·§9) |
| v5 | **"엔드포인트 이미 존재(ACI `test4`, Healthy)" 반영 + swagger 실측**: ① 문서 프레임을 "생성 설계"→**"연동 설계"**로 전환, 생성 섹션(§4~7·§9~12)은 참고/대안으로 격하 ② **§2 입출력 계약을 swagger 로 정정** — 실제는 `{"Inputs":{"input1":[...]}}`→`{"Results":{"WebServiceOutput0":[…,"Scored Labels"]}}` (이전 bare-array `[{...}]`→`{"result":…}` 가정은 **score.py 기준의 오추정**) ③ **§8 백엔드 연동 실계약으로 구현 완료**(azure.py 2함수·prediction.py·mock.py·tests, pytest green) ④ **EOL 팩트 정정**: CLI v1 종료 **2025-09-30**, SDK v1 종료 **2026-06-30**(v4의 "둘 다 2026-06-30" 오류 수정) ⑤ http 평문 보안 주의 추가 |
| **v6 (현재)** | **HTTPS 전환 범위 결정 반영**: 내부 사정으로 **HTTPS 전환은 현재 고려·결정하지 않음** → 산재한 "운영 HTTPS 이전" **권장을 범위 제외로 변경**(§0·§12), 재생성 사유에서 HTTPS 를 분리하고 **EOL 사유만 유지**(§0·§4 banner). http 평문은 **사실로는 명시 유지**(보완책: 키 노출 최소화·회전). |

---

## 0. 결론 요약 (먼저 읽기)

- **✅ 현황 — 엔드포인트 존재**: 모델이 **ACI 실시간 웹서비스 `test4`(classic Designer)** 로 배포되어 **Healthy**.
  REST/Swagger URI 생성됨 → 호출 가능. (즉 §9의 **P1 = Studio/Designer→ACI 경로가 사실상 채택**됨.)
- **🔑 핵심 정정(swagger 실측)**: 실제 입출력은 **Designer 웹서비스 봉투** —
  요청 `{"Inputs":{"input1":[…행…]},"GlobalParameters":{}}`, 응답 `{"Results":{"WebServiceOutput0":[…,"Scored Labels"]}}`.
  이전 §2/§8의 bare-array(`[{...}]`→`{"result":…}`) 가정은 **로컬 score.py 기준의 오추정**이었고, **실계약으로 정정·구현 완료**.
- **🟢 백엔드 연동 완료(무과금)**: `azure.py` 변환 2함수·`prediction.py`·`mock.py`·테스트를 실계약으로 수정, **pytest green**.
  남은 건 **키 주입 + `ML_CLIENT=azure` 스모크(승인 후)** 뿐.
- **⚠️ 보안 — http 평문**: ACI 엔드포인트는 `http://`(TLS 없음) → Bearer 키 평문 전송. **HTTPS 전환은 내부 사정으로 현재 고려·결정하지 않음**(테스트용으로 수용). 보완: 키 노출 최소화(로그·커밋 금지), 키 회전(primary/secondary) 운용.
- **⏳ 시한(EOL) 팩트(정정)**: **CLI v1 종료 2025-09-30(경과), SDK v1 종료 2026-06-30(임박)**.
  ACI/Designer 실시간은 v1(api-1) 계열 → **재생성·관리 도구 수명 짧음**. 장기엔 §0.1·v2문서 설계 C(재export)로 수렴 권장.
- **참고로 격하**: 엔드포인트 신규 **생성** 설계(§4~7 자원/비용/절차, §9 경로선택, §12 생성승인)는 **이미 존재하므로 지금 불필요**.
  향후 EOL 대응으로 **CLI/v2 재생성**을 택할 때만 다시 참조.

---

## 0.1 전제 분석: Designer 확정 + 모델 교체 가능

모델은 **Designer 기반 확정**이며, 동시에 현재 본은 **테스트용(교체 가능)**이다. 두 전제를 함께 반영한다.

### (A) Designer 확정의 함의 — 배포 경로 제약은 영구
- 클래식 Designer 모델(`ILearnerDotNet` + `azureml-designer-*`)의 **공식 배포 대상은 ACI/AKS**이며 **v2 관리형 온라인 엔드포인트는 미지원**(팩트체크 §11).
- 따라서 "모델만 바꾸면 MLflow no-code로 간다"는 v3의 가정은 **무효**(철회). 다음 모델도 Designer면 동일 제약이 따라온다.
- 결론: 배포는 §9의 선택지(P1 ACI / P2 v2-custom 비공식 / P3 AKS) 안에서 결정해야 함.

### (B) 모델 교체 가능의 함의 — stable vs 재도출
| 설계 항목 | 모델 교체 시 | 비고 |
|---|---|---|
| 워크스페이스/RG/구독/리전, 인증 | **유지** | 인프라 좌표는 모델 무관 |
| 배포 경로 선택(ACI/AKS/…)·절차 골격 | **유지** | Designer 유지되는 한 동일 |
| 비용·정리 정책(§5·7) | **유지** | 크기만 재평가 |
| 백엔드 호출 계층(`AzureMLClient`, 타임아웃·재시도·에러매핑) | **유지** | 추상화 레이어 목적 그대로 |
| **입출력 계약(§2)·변환 2함수·스키마(§8)** | **재도출** | 새 모델 `_schema.json`/`_samples.json`로 다시 확정 |
| 엔드포인트명 | 유지 가능 | 모델과 독립 |

### 권장 (의견)
1. **지금 무과금으로 확정할 것**: 백엔드 §8을 **제네릭(`list[dict]`)** 으로 맞추고 Mock E2E 유지. (Designer score.py의 `[{...}]` 입력 / `{"result":...}` 출력 계약은 Designer 유지 시 **모델이 바뀌어도 형태가 동일**하므로 변환 함수는 재사용 가능, 피처 목록만 §2 갱신.)
2. **배포 경로를 먼저 결정**(§9): 데모 신속·공식 지원이 중요하면 **P1(ACI)**, CLI·v2 일관성·학습이 중요하면 **P2를 로컬 검증 후 시도**. v1 EOL(2026-06-30) 때문에 P1은 단기용으로만.
3. **엔드포인트는 리허설 1회→삭제 또는 최종 모델 대기**(상시 운영 비권장 — 과금).

---

## 1. 현황 분석 (실측)

| 항목 | 값 | 확인 방법 |
|---|---|---|
| 구독 ID | `b5a82513-0077-4885-a2d3-6aa00c3cac5b` (대한상공회의소) | `az account show` |
| 리소스 그룹 | `project-1st-team-3` | `az ml workspace list` |
| 워크스페이스 | `team_3_ML` | 동상 |
| 리전 | `koreacentral` | 동상 |
| 모델 | `electricity_model` v1, **type=`custom_model`** | `az ml model show` |
| 모델 출처/생성 | Designer 학습 잡 `a12c0d7c-…`(ILearnerDotNet), 2026-06-22 생성("백엔드 연결용") | model 메타 |
| **기존 온라인 엔드포인트(v2)** | 0개 (v2 managed). 단 **classic ACI 웹서비스 `test4` 가 별도 존재**(v1, `az ml online-endpoint list`에 안 잡힘) | `az ml online-endpoint list` / 포털·ML_info.md §1 |
| 리전 VM 쿼터 | **Standard DSv2 Family vCPUs 0/50**, Total Regional 0/200 | `az vm list-usage -l koreacentral` |
| CLI 환경 | az 2.87.0 + ml ext 2.43.0, 로그인됨 | `az version` |
| 로컬 Docker | **없음** → `--local` 사전검증은 Docker 설치 후 가능 | `docker --version` |

### 1.1 모델 아티팩트 구조 (다운로드해 확인)
```
electricity_model/trained_model_outputs/
├── score.py            # init()/run() 채점 스크립트 (Designer 자동 생성)
├── conda_env.yaml      # python=3.8.10 + azureml-designer-* 의존성
├── data.ilearner       # 학습된 모델 바이너리 (ILearnerDotNet)
├── _schema.json        # 입력 컬럼 스키마 (8개 피처)
├── _samples.json       # 샘플 입력 행
├── model_spec.yaml / _meta.yaml
```
**의미**: `custom_model`은 본래 채점 스크립트+환경을 직접 작성해야 하나, 이 모델은 **Designer가 둘 다 동봉**해 재사용 가능(직접 작성 불필요). 단 동봉 스택이 구형이라 §3 R0 참조.

---

## 2. 입출력 계약 (swagger 실측 — 정정됨) ⚠️

> **정정(v5)**: 이전 본은 모델 아티팩트의 `score.py`/`_samples.json`(원시 행 배열)을 계약으로 추정했으나,
> **실제 배포는 Designer 서빙 레이어가 그 위를 감싸** 외부 HTTP 계약이 다르다. 아래는 **배포된 `test4` swagger.json 실측**.
>
> ⚠️ **이력 주의(2026-06-23)**: 아래 표는 **구 `test4` 당시** 계약이다. 현 운영 엔드포인트(`final-endpoint`)는
> `avg_temp`→**`avg_temperature`** 개명 + `prev_year_usage`·`current_usage` **int64→double** 로 바뀌었다.
> **현행 계약은 [`../azure/info.md`](../azure/info.md) §5.1** 및 코드 단일 진실원 `app/schemas/prediction.py::EXAMPLE_INPUT_ROW` 참조.

**요청 본문(`POST /score`, `Authorization: Bearer {key}`, http):**
```json
{"Inputs": {"input1": [
  {"prev_year_usage": 76, "avg_temp": -0.46, "avg_humidity": 66.55, "total_rainfall": 21.1,
   "current_usage": 53, "thi": 36.1076813, "month_sin": 0.5, "month_cos": 0.8660254037844387}
]}, "GlobalParameters": {}}
```
| 컬럼(필수 8개) | 타입(swagger) |
|---|---|
| prev_year_usage / current_usage | integer (int64) |
| avg_temp / avg_humidity / total_rainfall / thi / month_sin / month_cos | number (double) |

**응답 본문:** `{"Results": {"WebServiceOutput0": [ {입력 피처 에코…, "Scored Labels": <double>} ]}}`
— 입력 행마다 1개 출력 행, 예측값은 **`Scored Labels`** 컬럼. 백엔드는 이 값만 추출해 `predictions: list[number]` 로 반환(§8). 헬스: `GET /` → `"Healthy"`(Bearer 필요).

> 이전 백엔드 가정(`{"input_data":…}`/`"predictions"`)은 이 계약과 **불일치(실버그)**였고 → §8에서 근본 수정(구현 완료).

---

## 3. 리스크 / 근본 분석

| # | 리스크 | 근본 원인 | 영향 | 대응 |
|---|---|---|---|---|
| **R0** | **클래식 Designer 모델은 v2 관리형 엔드포인트 공식 미지원** | "클래식 프리빌트(v1) 컴포넌트 배포는 v2 관리형 온라인 엔드포인트 미지원"(공식, §11). 공식 대상은 ACI/AKS. 게다가 동봉 conda는 구형(py3.8.10 + `azureml-designer-serving==0.0.13`) | v2 managed endpoint 시도 시 빌드/임포트/init 실패 가능, 성공해도 비공식 | **경로 결정**(§9): P1(ACI, 공식) 또는 P2(v2-custom, 비공식—**로컬 `--local`로 먼저 검증**). v2 시도 실패는 `get-logs`로 진단 |
| **R0b** | **SDK/CLI v1 지원 종료** | v1 deprecated 2025-03-31. **CLI v1 종료 2025-09-30(경과)**, **SDK v1 종료 2026-06-30(임박)** | ACI/Designer(v1) 재생성·관리 도구 수명 짧음 | 이미 배포된 `test4` 는 동작하나, **재생성·장기 운영은 v2 경로(설계 C 재export)로 재설계** 필요 |
| R1 | VM 코어 쿼터 | 관리형 엔드포인트는 VM 패밀리 쿼터 소비 | 부족 시 `OutOfQuota` | **실측 0/50 → 여유**. DS2_v2=4코어 필요. (AML 전용 쿼터가 별도 0으로 막힌 경우만 예외 → Studio 확인) |
| R2 | 상시 과금 | 엔드포인트는 전용 VM 24/7 점유(요청 0건도 과금) | 비용 | 데모 후 **삭제**(§7). 비용표 §5 |
| R3 | 환경 빌드 시간 | 구형 pip 의존성 해석 | 첫 배포 5~15분+ | 정상 범주. 진행률은 `get-logs` |
| R4 | 모델 경로 가정 | `score.py`가 `AZUREML_MODEL_DIR/trained_model_outputs` 참조 | 불일치 시 init 실패 | **공식 확인**: `AZUREML_MODEL_DIR`는 아티팩트 루트를 가리킴. 다운로드 구조상 `trained_model_outputs/`가 루트 하위 폴더로 보존 → 경로 **일치(고신뢰)**. 배포 후 init 로그로 최종 확인 |
| R5 | 콜드스타트/프로브 | 모델 로드(.ilearner+designer 임포트) 지연 + 소형 SKU | `ResourceNotReady`(컨테이너 준비 지연) | 작은 SKU 주의(공식). 발생 시 DS3_v2로 상향, `liveness/readiness probe`·`request_settings` 조정 |
| R6 | 이름 충돌 | 엔드포인트명은 리전 내 구독 단위 유일(3~32자, 영문 시작) | 생성 실패 | 유니크 명 사용 |

> 설계 원칙(stateless·오토스케일)은 **App Service 백엔드** 적용 사항이고, ML 엔드포인트는 별개 관리형 리소스다. 백엔드는 scoring URI/key만 주입받아 호출한다.

---

## 4. 리소스 설계 (경로 P2 — v2 관리형, 비공식)

> 🗄️ **참고/대안(v5)**: 엔드포인트는 **이미 ACI 로 존재**하므로 §4~7(생성)은 **지금 실행 불필요**. 향후 EOL 대응으로 **CLI/v2 재생성**을 택할 때만 참조.
> ⚠️ **기존 `test4` 의 URI/키는 §6 방식이 아님**: URI 는 이미 확보([`../azure/ML_info.md`](../azure/ML_info.md) §1), **키는 포털 "Consume" 탭**(또는 v1 `az ml service get-keys`)에서 얻는다. §6 의 `az ml online-endpoint show/get-credentials`(v2 관리형)는 이 classic ACI 엔드포인트엔 적용되지 않는다.
>
> 이 절과 §5·§6은 **P2 경로**(§9)에 해당. P1(ACI)을 택하면 본 절 대신 Studio 배포 마법사를 따른다.

| 항목 | 결정 | 근거 |
|---|---|---|
| 엔드포인트 종류 | **Managed Online Endpoint** (v2) | 서버리스 관리형, CLI v2 표준 |
| 인증 모드 | `auth_mode: key` | 백엔드가 `Authorization: Bearer {key}` 호출(키 만료 없음). 설계 일치 |
| 모델 | `azureml:electricity_model:1` (등록본 재사용) | 재등록 불필요 |
| 채점 스크립트 | 모델 동봉 `score.py` → 로컬 `onlinescoring/`로 복사 후 code 업로드 | custom_model 필수 |
| 환경 | 모델 동봉 `conda_env.yaml` + 베이스 이미지 | Designer 서빙 스택 |
| 베이스 이미지 | `mcr.microsoft.com/azureml/openmpi4.1.0-ubuntu22.04:latest` | 공식 예제 기본. conda가 py3.8 별도 생성 |
| **VM SKU** | **`Standard_DS2_v2`**(2 vCPU/7GB) 우선, R5 시 `Standard_DS3_v2`(4 vCPU/14GB) | 둘 다 **지원 SKU 목록 확인됨**. 비용/쿼터 최소화. 쿼터=ceil(1.2×1)×코어 → DS2_v2=4, DS3_v2=8 |
| 인스턴스 수 | `1` | 데모 규모(프로덕션 권장은 3+) |
| 트래픽 | blue 배포 100% | 단일 배포 |

### 4.1 작업 디렉터리 (배포용; `.gitignore` 권장 — 산출물·요청샘플)
```
deploy/ml-endpoint/
├── endpoint.yml
├── deployment.yml
├── onlinescoring/
│   └── score.py            # 모델 아티팩트에서 복사
├── conda_env.yaml          # 모델 아티팩트에서 복사
└── sample-request.json     # _samples.json 기반 검증용
```

### 4.2 endpoint.yml
```yaml
$schema: https://azuremlschemas.azureedge.net/latest/managedOnlineEndpoint.schema.json
name: electricity-ep-3team
auth_mode: key
```

### 4.3 deployment.yml
```yaml
$schema: https://azuremlschemas.azureedge.net/latest/managedOnlineDeployment.schema.json
name: blue
endpoint_name: electricity-ep-3team
model: azureml:electricity_model:1
code_configuration:
  code: ./onlinescoring
  scoring_script: score.py
environment:
  conda_file: ./conda_env.yaml
  image: mcr.microsoft.com/azureml/openmpi4.1.0-ubuntu22.04:latest
instance_type: Standard_DS2_v2
instance_count: 1
# (선택) R5 콜드스타트 대비 — 필요 시 주석 해제·조정
# request_settings:
#   request_timeout_ms: 10000        # 기본값보다 상향(채점 지연 대비)
# readiness_probe:
#   initial_delay: 30
#   timeout: 10
#   period: 10
#   failure_threshold: 30
```

---

## 5. 비용 추정 (R2)

> 관리형 엔드포인트는 요청이 없어도 VM이 상시 과금. 아래는 **개략 추정**(공개 단가 기준, koreacentral 실단가·환율은 가격 계산기로 확인 권장).

| SKU | vCPU/RAM | 시간당(개략) | 월(상시, ≈730h) |
|---|---|---|---|
| Standard_DS2_v2 | 2 / 7GB | ≈ $0.146 | ≈ $107 |
| Standard_DS3_v2 | 4 / 14GB | ≈ $0.293 | ≈ $214 |

→ **데모/검증 후 즉시 삭제**가 기본 정책(§7). 상시 운영이 필요 없으면 "쓸 때만 생성"이 가장 저렴.

> 🗄️ **실제 배포는 위 표와 무관**: `test4` 는 **ACI(0.1 vCPU / 0.5GB)** 로, 컨테이너 단위 과금이라 위 관리형 VM 단가보다 **현저히 저렴**. 위 표는 P2(v2 managed) 재생성 시에만 적용.

---

## 6. 실행 절차 (경로 P2, ⚠️ 승인 후) — 단계별

```bash
# 0) 공통 변수 + 기본값 (이후 -g/-w 생략)
SUB=b5a82513-0077-4885-a2d3-6aa00c3cac5b
RG=project-1st-team-3
WS=team_3_ML
EP=electricity-ep-3team
az account set -s $SUB
az configure --defaults group=$RG workspace=$WS

# 1) 배포 자산 준비 (모델 아티팩트에서 score.py / conda 복사)
az ml model download -n electricity_model -v 1 --download-path ./_dl
mkdir -p deploy/ml-endpoint/onlinescoring
cp ./_dl/electricity_model/trained_model_outputs/score.py        deploy/ml-endpoint/onlinescoring/
cp ./_dl/electricity_model/trained_model_outputs/conda_env.yaml  deploy/ml-endpoint/
#  (sample-request.json 은 _samples.json 내용을 그대로 사용)

# 2) (선택·무과금 권장) 로컬 검증 — Docker 필요(현재 미설치)
# az ml online-endpoint  create  --local -n $EP -f deploy/ml-endpoint/endpoint.yml
# az ml online-deployment create --local -n blue --endpoint $EP -f deploy/ml-endpoint/deployment.yml
# az ml online-endpoint  invoke  --local -n $EP --request-file deploy/ml-endpoint/sample-request.json

# 3) 엔드포인트 생성 (수 초~수십 초)
az ml online-endpoint create -f deploy/ml-endpoint/endpoint.yml

# 4) blue 배포 생성 + 트래픽 100% (환경 빌드로 5~15분+)
az ml online-deployment create -f deploy/ml-endpoint/deployment.yml --all-traffic

# 5) 스모크 테스트
az ml online-endpoint invoke -n $EP --request-file deploy/ml-endpoint/sample-request.json

# 6) 백엔드 주입용 값 추출 (KEY는 .env/App Settings에만, 로그·커밋 금지)
SCORING_URI=$(az ml online-endpoint show -n $EP --query scoring_uri -o tsv)
ENDPOINT_KEY=$(az ml online-endpoint get-credentials -n $EP --query primaryKey -o tsv)
echo "AZURE_ML_SCORING_URI=$SCORING_URI"
```
> 실패 진단(근본 원인): `az ml online-deployment get-logs -n blue --endpoint $EP` → 환경 빌드/임포트(R0)·경로(R4)·프로브(R5) 구분.

---

## 7. 정리 / 비용 통제 (중요)
```bash
# 데모 종료 후 과금 중단 — 엔드포인트 삭제 시 하위 배포도 함께 삭제
az ml online-endpoint delete -n $EP --yes
```
> 미사용 시 **삭제가 기본**. 재생성은 §6으로 수 분 내 가능. (선택) 일과 후 자동 삭제 스케줄도 검토 가능.

---

## 8. 백엔드 연동 — 계약 정합화 ✅ 구현 완료 (실버그 수정)

이전 코드는 **가정값**(`{"input_data":…}`/`"predictions"`)이라 §2 실계약과 어긋났다(실버그). **swagger 실측 계약으로 근본 수정 완료**, pytest green.

> **모델 가변성 반영(§0.1)**: 모델이 교체될 수 있어 입력은 **제네릭(`list[dict]`)** 으로 둔다(피처를 코드에 못박지 않음).
> 출력 파싱도 **출력 포트명에 의존하지 않게**(첫 배열 채택) 작성해 교체 내성을 확보.

**수정된 문제점 4건**
1. `prediction.py`의 `inputs: list[float] | dict` → **`list[dict[str, Any]]` + `min_length=1`** (행 배열).
2. `_to_aml_payload`가 `{"input_data": …}` → **`{"Inputs": {"input1": …}, "GlobalParameters": {}}`** 봉투.
3. `_from_aml_response`가 `"predictions"` → **`Results.WebServiceOutput0`**(포트명 비의존: 첫 배열).
4. `mock.py`/`tests`를 행 배열 계약으로 갱신(+ 빈 배열·비-dict 422 케이스).

**`app/schemas/prediction.py`** (적용본)
```python
class PredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")          # 최상위 미지 필드 거부
    inputs: list[dict[str, Any]] = Field(min_length=1) # 행 배열(제네릭, 모델 교체 내성)
```
**`app/ml/azure.py` — 변환 2함수** (적용본)
```python
@staticmethod
def _to_aml_payload(request: PredictRequest) -> dict[str, Any]:
    # Designer 웹서비스 형식. 입력 포트명은 classic Designer 기본값 'input1'.
    return {"Inputs": {"input1": request.inputs}, "GlobalParameters": {}}

@staticmethod
def _from_aml_response(data: Any) -> list[Any]:
    # {"Results": {"WebServiceOutput0": [ {..., "Scored Labels": ...} ]}}
    # 출력 포트명이 모델마다 달라도 Results 의 첫 배열을 취한다(교체 내성).
    if isinstance(data, dict):
        results = data.get("Results")
        if isinstance(results, dict):
            for value in results.values():
                if isinstance(value, list):
                    return value
    return data if isinstance(data, list) else [data]
```
> `predict()`는 `httpx ... json=payload` 로 **순수 dict/list** 를 직렬화 — 위 페이로드가 이를 만족.
> **출력 표현(확정)**: 각 출력 행의 **`Scored Labels`** 값만 추출해 `predictions: list[number]` 로 반환 →
> **Mock 과 동일한 형태로 통일**(추상화 일관성·프론트 친화). `Scored Labels` 키가 없으면(모델/스키마 교체) 행 전체를 보존(교체 내성).

**참고(최종 모델 확정 후): 타입드 스키마로 검증 강화** — 8개 피처를 `FeatureRow`(BaseModel)로 고정하면 누락/오타를 422로 차단. 단 **모델 교체 시 재작성** 필요하므로 계약 확정 전엔 제네릭 유지.

**남은 작업(연동 마무리)**
- `.env`/App Settings: `ML_CLIENT=azure`, `AZURE_ML_SCORING_URI`, **`AZURE_ML_AUTH_PRI_KEY`/`AZURE_ML_AUTH_SEC_KEY`(엔드포인트 primary/secondary 키, 미커밋)**. 키는 워크스페이스 단일 키가 아니라 **`test4` Consume 탭**에서 확보(이미 `.env` 저장).
- `app/ml/comsume.py` 스모크(`python -m app.ml.comsume`, `.env` 자동 로드) → `ML_CLIENT=azure` 로 `/api/v1/predict` E2E(실연동 **승인 후**).

---

## 9. 배포 경로 선택지 (Designer 확정 기준)

> 🗄️ **실현된 결과(v5)**: 실제로는 **P1(Studio/Designer→ACI)** 로 배포됨(`test4`). 아래는 의사결정 기록이며, **재생성 검토 시에만** 참조.

클래식 Designer 모델은 v2 관리형 엔드포인트를 **공식 미지원**(R0)이므로, 경로를 먼저 정한다.

### P1 — Designer/Studio → ACI (공식 지원, no-code)
- 경로: Studio **Models → Use this model → Web service → Azure Container Instance** → `score.py`/`conda_env.yaml` 업로드 → Deploy. (또는 Designer에서 실시간 추론 파이프라인 후 배포)
- 장점: **공식 지원**, 환경 자동 구성, 테스트용 저비용(ACI는 컨테이너 단위 과금).
- 단점: **SDK/CLI v1 기반 → 2026-06-30 지원 종료(R0b)**. CLI가 아닌 **UI 중심**. 산출 엔드포인트는 v1 웹서비스.
- 백엔드 영향: scoring URI/key는 동일하게 추출되며, `AzureMLClient` 호출 계약(§2)은 그대로 적용.

### P2 — v2 관리형 온라인 엔드포인트 + 동봉 score.py/conda (비공식, CLI)
- 경로: §4·§6의 `az ml online-endpoint`/`online-deployment`. 모델을 `custom_model`로 두고 표준 init/run 채점.
- 장점: **CLI·v2 일관성**, 재현성(YAML 커밋), App Service 운영 시점과 도구 통일, 학습 가치.
- 단점: **공식 미지원(R0)** — 구형 conda 빌드/`azureml-designer-serving` 호환 실패 가능. 성공해도 지원 보장 없음.
- 필수 선검증: **로컬 `--local`(Docker) 또는 1회 배포 후 `get-logs`**. 막히면 P1로 전환.

### P3 — AKS / Kubernetes 온라인 엔드포인트
- 클러스터 상시 비용·운영 부담 → **데모/소규모엔 과대**. 제외 권장.

### 9.1 의사결정 매트릭스
| 기준 | P1 (ACI/Studio) | P2 (v2 managed CLI) |
|---|---|---|
| 공식 지원 | ◎ | ✗ (비공식) |
| CLI·v2 일관성/재현성 | △ (UI) | ◎ |
| 성공 확실성(단기) | ◎ | △ (선검증 필요) |
| 수명(장기) | ✗ (v1 EOL 2026-06-30) | △ (현행 도구지만 비공식) |
| 비용(테스트) | ◎ (ACI) | ○ (전용 VM) |

> **의견**: "지금 데모를 확실히 띄우는 것"이 목표면 **P1(ACI)**. "CLI/v2로 파이프라인을 학습·표준화"가 목표면 **P2를 로컬 검증 후 시도**하고 실패 시 P1로 폴백. 어느 쪽이든 **백엔드 §8(제네릭)은 선행**해 두면 손해가 없다.

---

## 10. 검증 기준
- (완료) 엔드포인트 `Healthy` + REST/Swagger URI 존재 + swagger 계약 실측(§2).
- (완료) §8 백엔드 수정 후 **pytest green**(22 passed).
- (완료) 스모크: `python -m app.ml.comsume` → `{"Results":{"WebServiceOutput0":[…,"Scored Labels"]}}` 정상.
- (완료) **운영 배포**: App Service `ML_CLIENT=azure` → `/health` 200, `/api/v1/predict` 200(`predictions:[87.55…]`), 무키 401. 배포는 `deploy.sh`(OneDeploy).

---

## 11. 근거 (공식 문서)
- 온라인 엔드포인트 배포(CLI v2) — endpoint/deployment YAML, `auth_mode`, `code_configuration.scoring_script`, `--all-traffic`, `show`/`get-credentials`:
  https://learn.microsoft.com/en-us/azure/machine-learning/how-to-deploy-online-endpoints?view=azureml-api-2&tabs=cli
- 모델 사양/`AZUREML_MODEL_DIR`(아티팩트 루트를 가리킴):
  https://learn.microsoft.com/en-us/azure/machine-learning/concept-online-deployment-model-specification?view=azureml-api-2
- 인증(key/aml_token/aad_token):
  https://learn.microsoft.com/en-us/azure/machine-learning/how-to-authenticate-online-endpoint?view=azureml-api-2
- 쿼터(코어 = ceil(1.2×인스턴스)×코어/VM):
  https://learn.microsoft.com/en-us/azure/machine-learning/how-to-manage-quotas?view=azureml-api-2
- 지원 VM SKU 목록(DS2_v2/DS3_v2 포함, 소형 SKU 프로브 주의):
  https://learn.microsoft.com/en-us/azure/machine-learning/reference-managed-online-endpoints-vm-sku-list?view=azureml-api-2
- **Designer 모델 배포 = ACI/AKS (api-1/v1), SDK v1 지원 종료 2026-06-30 명시**:
  https://learn.microsoft.com/en-us/azure/machine-learning/how-to-deploy-model-designer?view=azureml-api-1
- **Designer no-code 배포 튜토리얼(ACI/AKS 컴퓨트 선택)**:
  https://learn.microsoft.com/en-us/azure/machine-learning/tutorial-designer-automobile-price-deploy?view=azureml-api-1
- 클래식 프리빌트(v1) 컴포넌트의 v2 관리형 엔드포인트 미지원 / Designer(v1) 개념:
  https://learn.microsoft.com/en-us/azure/machine-learning/concept-designer?view=azureml-api-1

---

## 12. 검토 요청 (확인 필요) — v5 갱신

생성 경로/SKU/삭제 등 질문은 **엔드포인트가 이미 ACI 로 존재**하므로 대부분 해소. 남은 결정만:

1. ~~키 확보·주입~~ **(완료)**: `test4` Consume 탭의 **primary/secondary 키**를 `.env` 의 `AZURE_ML_AUTH_PRI_KEY`/`AZURE_ML_AUTH_SEC_KEY` 로 저장(미커밋). (워크스페이스 단일 키는 존재하지 않음 — 엔드포인트 단위 키.)
2. **실연동 스모크 승인**: `ML_CLIENT=azure` 로 1건 호출(외부 호출) — 진행 승인?
3. ~~출력 표현~~ **(확정)**: `Scored Labels`만 추출해 `predictions: list[number]` 로 반환 — **Mock 과 동일 형태**로 통일(키 없으면 행 보존). 프론트가 다른 형태(전체 행 등)를 원하면 재조정.
4. **운영 전환 시**: v1 EOL(SDK 2026-06-30) 대응으로 **v2 경로 재설계**(설계 C 재export) 시점 — 언제 다룰지? (※ **HTTPS 전환은 내부 사정으로 현재 범위 제외** — 결정·고려 보류.)
5. (선택) `test4` 는 테스트용 — **최종 모델 확정 시** §2 피처 갱신 + (원하면) 타입드 스키마로 강화.

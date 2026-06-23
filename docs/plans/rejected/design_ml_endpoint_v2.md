# 클래식 Designer 모델을 **v2 온라인 엔드포인트**로 올리기 — 고려요소 & 설계 (반려/rejected)

> ## 🗄️ REJECTED — 보존용(역사적 기록). 실행하지 말 것.
> **2026-06-22 갱신**: 팀(예찬 김)이 모델을 **ACI 실시간 웹서비스(`test4`)로 이미 배포**했고
> 상태 **Healthy**, 호출 가능. 즉 본 문서가 다루는 **"v2 managed 엔드포인트로 강제 이전"
> 경로는 채택되지 않았다**(공식 지원 경로인 ACI 로 갔다). 따라서 BYOC/py3.8 핀/`inference_config`
> 등 본 문서의 작업은 **현재 불필요**하다.
> - 실제 엔드포인트 정보·실측 계약: [`../../azure/info.md`](../../azure/info.md)
> - 현행 연동 설계: [`design_ml_endpoint.md`](../design_ml_endpoint.md)
> - 본 문서의 가치: 향후 **HTTPS/EOL 대응으로 v2 이전이 필요해질 때**의 사전 분석으로만 참조
>   (설계 C = v2 네이티브 재export 가 여전히 EOL-free 정답).
>
> ---
>
> *(이하 원문 보존)*
>
> 목적: `electricity_model`(Azure ML **Designer 클래식**, `ILearnerDotNet`)을 **반드시 v2 managed online endpoint**로 서빙하기 위한 고려요소와 설계.
> 상태: ~~검토·승인 대기~~ → **SUPERSEDED**. 작성 근거: 공식 문서 팩트체크(§9) + CLI/아티팩트 실측.
> 관계 문서: 배포 경로 전반·비용·백엔드 연동은 [design_ml_endpoint.md](../design_ml_endpoint.md) 참조. 본 문서는 **"v2로 어떻게 동작시키나"** 에 집중.

---

## 0. 한 줄 결론

클래식 Designer 모델은 **표준 v2 배포(동봉 conda 그대로)로는 깨지기 쉽다 — 근본 원인은 "모델 런타임=py3.8 vs v2 추론서버=py3.9+"의 버전 충돌**.
v2로 올리는 방법은 두 갈래다: **(설계 B) py3.8을 고정한 BYOC 커스텀 컨테이너**(가장 확실) 또는 **(설계 A) 동봉 conda를 py3.8 호환 버전으로 핀 고정해 표준 배포**(간단하나 취약). 장기적으론 **(설계 C) 모델을 v2 네이티브 형식으로 재export**가 유일하게 EOL-free.

---

## 1. 근본 제약 분석 (왜 단순 v2 배포가 위험한가)

v2 managed online endpoint는 컨테이너 안에서 **Azure ML 추론 서버(`azureml-inference-server-http`)**가 `score.py`의 `init()`/`run()`을 호출하는 구조다. 그런데:

| 구성요소 | 요구/특성 | 출처 |
|---|---|---|
| 모델 동봉 `conda_env.yaml` | **python=3.8.10**, `azureml-designer-classic-modules==0.0.182`, `azureml-designer-serving==0.0.13` | 아티팩트 실측 |
| `azureml-inference-server-http`(v2 추론서버) | **Python 3.8 지원 중단 → 3.9+ 필요** | 공식(§9) |
| 모델 로딩 런타임 | `azureml.studio.*` / `azureml.designer.serving.*` (py3.8 빌드) | `score.py` 실측 |

→ **충돌**: 최신 추론서버는 py3.9+를 원하는데, 모델 런타임은 py3.8에 묶여 있다.
→ 동봉 conda를 "그대로" 쓰면, conda가 끌어오는 `azureml-defaults`가 **(구버전이면)** py3.8 호환 추론서버를 함께 설치해 동작할 *수도* 있으나, **버전 해석이 최신으로 끌려가면 즉시 깨진다**. 이 불확정성이 핵심 리스크.

> 결론: v2로 가려면 **"파이썬/추론서버 버전을 명시적으로 py3.8에 고정"** 하는 설계가 필수다. 운에 맡기면 안 된다.

---

## 2. v2에서 동작시키는 원리

1. 모델은 이미 `custom_model`로 등록됨 → v2는 이를 컨테이너의 `AZUREML_MODEL_DIR`에 마운트.
   - 기본 마운트: `/var/azureml-app/azureml-models/electricity_model/1` (아래에 `trained_model_outputs/` 보존).
   - `score.py`의 `os.path.join(AZUREML_MODEL_DIR, 'trained_model_outputs')` 와 **일치**(공식: AML이 `AZUREML_MODEL_DIR` 주입).
2. `score.py`는 표준 `init()`/`run()` 계약 → **추론서버만 호환되면** 그대로 동작.
3. 추론서버 호환을 확보하는 2가지 방법:
   - **표준 환경(설계 A)**: `conda_file + 베이스 이미지` → AML이 conda 위에서 표준 서버를 띄움(`/score` 자동 제공, `inference_config` 불필요).
   - **BYOC(설계 B)**: 내가 만든 Docker 이미지로 직접 서버를 띄우고 `inference_config`로 liveness/readiness/scoring **라우트를 명시**(공식: BYOC에선 `inference_config` 필수).

---

## 3. 고려요소 체크리스트 (v2 적용 시)

| 분류 | 고려요소 | 결정/주의 |
|---|---|---|
| **런타임 호환** | py3.8 ↔ 추론서버 py3.9+ 충돌 | **py3.8 고정** + py3.8 호환 `azureml-inference-server-http`/`azureml-defaults` **버전 핀** (최우선) |
| 모델 경로 | `AZUREML_MODEL_DIR/trained_model_outputs` | 등록 구조상 일치. `model_mount_path` 커스텀 시 경로 재확인 |
| 추론서버 라우트 | BYOC면 liveness/readiness/scoring 포트·경로 | 로컬에서 실측 후 `inference_config`에 기입(예: `azmlinfsrv` 기본 `/score`, port 5001 — **로컬 확인 필수**) |
| 환경 빌드 | 구형 pip 의존성 해석 | 첫 빌드 5~15분+, 일부 패키지 yank 가능 → **버전 핀**으로 재현성 확보 |
| 콜드스타트/프로브 | `.ilearner`+designer 임포트 지연 | `request_settings.request_timeout_ms`↑, `readiness_probe` 여유. 소형 SKU는 `ResourceNotReady` 주의 |
| 인증 | `auth_mode: key`(백엔드 Bearer 호출) | 키 만료 없음. 설계 일치 |
| 쿼터/SKU/비용 | DSv2 0/50(실측 여유), DS2_v2 권장 | 상세는 design_ml_endpoint.md §4·5 |
| 재현성 | YAML+Dockerfile 버전관리 | v1 UI 배포와 달리 코드화 가능(본 설계의 장점) |
| 로깅/디버깅 | `get-logs`, 로컬 추론서버 디버그 | 로컬 검증으로 클라우드 과금 전 진단 |
| **EOL 리스크** | py3.8/designer 스택은 EOL 계열 | BYOC라도 **기술부채**. 장기엔 설계 C 권장 |
| 개발환경 | **로컬 Docker 필요**(현재 미설치) | 설치하거나 **ACR 클라우드 빌드** 사용 |

---

## 4. 설계안 비교

### 설계 A — 표준 환경(conda) + 버전 핀 (간단, 취약)
- `deployment.yml`에 `environment.conda_file` + 베이스 이미지. **단, 동봉 conda를 그대로 쓰지 말고** py3.8 호환으로 핀 고정.
- conda 수정 예(요지): `python=3.8.10` 유지 + `azureml-defaults==<py3.8 지원 마지막>` / `azureml-inference-server-http==<py3.8 지원 마지막>` 명시.
- 장점: Dockerfile 불필요, YAML만으로 배포. `inference_config` 불필요(표준 `/score`).
- 단점: pip 해석이 최신으로 끌릴 위험·base 이미지와의 궁합 → **실패 가능성 잔존**. "되면 가장 싸게 끝".

### 설계 B — BYOC 커스텀 컨테이너 (확실, 통제력↑) ★권장
- py3.8을 못박은 Docker 이미지를 직접 빌드 → ACR push → `environment.image` + `inference_config`로 배포.
- Dockerfile **스케치**(검증 전, 라우트/버전은 로컬 확인 후 확정):
  ```dockerfile
  FROM mcr.microsoft.com/azureml/openmpi4.1.0-ubuntu20.04:latest   # conda 포함 베이스
  COPY conda_env.yaml /tmp/conda_env.yaml
  # py3.8 환경 생성 + py3.8 호환 추론서버 핀
  RUN conda env create -n serve -f /tmp/conda_env.yaml && \
      conda run -n serve pip install "azureml-inference-server-http==<py38-호환>"
  ENV AZUREML_ENTRY_SCRIPT=score.py
  EXPOSE 5001
  CMD ["conda","run","--no-capture-output","-n","serve", \
       "azmlinfsrv","--entry_script","score.py","--port","5001"]
  ```
- `deployment.yml`(요지):
  ```yaml
  environment:
    image: <acr>.azurecr.io/designer-electricity:1
    inference_config:
      liveness_route:  { port: 5001, path: / }
      readiness_route: { port: 5001, path: / }
      scoring_route:   { port: 5001, path: /score }
  model: azureml:electricity_model:1
  instance_type: Standard_DS2_v2
  instance_count: 1
  ```
- 장점: **파이썬/서버 버전 완전 통제 → 가장 확실**. 재현성↑.
- 단점: Dockerfile 유지·ACR 필요. "커스텀 이미지 문제는 MS 지원이 제한적"(공식 경고).

### 설계 C — 모델을 v2 네이티브로 재export (근본해결, EOL-free) ★전략 권장
- 데이터 사이언티스트가 동일 학습을 **sklearn/MLflow 등 표준 형식**으로 저장 → v2 **no-code 또는 표준 custom 배포**(py3.9+) 가능.
- 장점: 버전 충돌·EOL 부채 **소멸**, no-code 배포, Swagger 계약 자동.
- 단점/제약: **"Designer 사용 확정"** 과 충돌할 수 있음(클래식 Designer는 `.ilearner`만 산출). → Designer로 *만들되* 산출물만 표준화 가능한지 확인 필요(§8 질문).

### 비교표
| 기준 | A(conda 핀) | B(BYOC) | C(재export) |
|---|---|---|---|
| 성공 확실성 | △ | ◎ | ◎ |
| 구축 난이도 | 낮음 | 중간(Docker/ACR) | 모델측 작업 필요 |
| 재현성 | ○ | ◎ | ◎ |
| EOL 부채 | 있음 | 있음 | **없음** |
| Designer 확정과 양립 | ○ | ○ | △(확인필요) |

---

## 5. 권장 진행 (단계적, 과금 최소)

1. **로컬 Docker 확보**(설치 or ACR 빌드 결정). 로컬 검증 없이 클라우드 반복은 과금·시간 낭비.
2. **설계 A를 로컬 `--local`로 1차 시도**(가장 싸게 끝날 수 있음). 깨지면 원인(`get-logs`)을 보고 **설계 B로 전환**.
3. 설계 B: Dockerfile 빌드 → 로컬 추론서버로 **라우트/스코어 실측**(`curl /score`) → `inference_config` 확정.
4. 로컬 통과 후에만 **클라우드 배포**(승인) → `invoke` 검증 → URI/key 추출 → 백엔드 연동.
5. 데모 후 **삭제**(과금 통제).
6. 병렬로 **설계 C 가능성**을 모델 담당자와 확인(가능하면 장기적으로 C로 수렴).

> 무과금 선행: 백엔드 계약 정합화(design_ml_endpoint.md §8, 제네릭 `list[dict]`)는 경로와 무관하게 지금 진행 가능.

---

## 6. 검증 기준
- 로컬: `azmlinfsrv` 컨테이너가 liveness 200 + `/score`로 `_samples.json` 정상 응답.
- 클라우드: `online-endpoint show` → `Succeeded`/`scoring_uri`, `invoke` → `{"result":[...]}`.
- E2E: 백엔드 `ML_CLIENT=azure`로 `/api/v1/predict` 통과.

## 7. 롤백/정리
- 실패 시 `online-deployment get-logs`로 진단 → 설계 A↔B 전환.
- 미사용 시 `az ml online-endpoint delete -n <ep> --yes` (하위 배포 동시 삭제).

---

## 8. 확인 필요 (질문)

1. **설계 C 가능 여부 (가장 중요)**: 모델을 **Designer로 만들되 산출물을 표준(sklearn/MLflow)으로 저장**할 수 있나요? 가능하면 버전충돌·EOL이 근본 해소됩니다. (불가하면 B로 확정)
2. **로컬 Docker / 빌드 환경**: 로컬에 Docker 설치가 가능한가요, 아니면 **ACR 클라우드 빌드**(`az acr build`)로 이미지를 구울까요? (BYOC 필수 전제)
3. **목표 수명**: 단기 데모용인가요, 운영 지속인가요? (단기면 A/B, 지속이면 C 강권)
4. **승인 범위**: 엔드포인트 생성(과금) 승인 + SKU(`Standard_DS2_v2` 권장) + 엔드포인트명 확정?

---

## 9. 근거 (공식 문서 — 팩트체크)
- **v2 커스텀 컨테이너(BYOC) 배포** — `inference_config`(liveness/readiness/scoring), `model_mount_path`, 라우트 필수, "BYOC엔 inference_config 필수":
  https://learn.microsoft.com/en-us/azure/machine-learning/how-to-deploy-custom-container?view=azureml-api-2&tabs=cli
- **`azureml-inference-server-http`** — Python 3.8 지원 중단(3.9+), `init()`/`run()` 계약, `azmlinfsrv`:
  https://pypi.org/project/azureml-inference-server-http/
  https://learn.microsoft.com/en-us/azure/machine-learning/how-to-inference-server-http?view=azureml-api-2
- **모델 마운트/`AZUREML_MODEL_DIR`**:
  https://learn.microsoft.com/en-us/azure/machine-learning/concept-online-deployment-model-specification?view=azureml-api-2
- **클래식 Designer = ACI/AKS(v1) 배포, 클래식 컴포넌트와 v2 혼용 불가, SDK v1 종료 2026-06-30 / CLI v1 종료 2025-09-30**:
  https://learn.microsoft.com/en-us/azure/machine-learning/how-to-deploy-model-designer?view=azureml-api-1
  https://learn.microsoft.com/en-us/azure/machine-learning/how-to-migrate-from-v1?view=azureml-api-2
- 온라인 엔드포인트 배포/인증/쿼터/SKU: design_ml_endpoint.md §11 참조.

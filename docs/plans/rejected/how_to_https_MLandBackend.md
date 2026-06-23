# Backend ↔ ML 간 HTTPS(TLS) 적용 방안 — 연구/제안 (보류 결정됨)

> **작성일:** 2026-06-23 · **상태:** 🔴 **보류(Reject) — 2026-06-23 결정.** 프로젝트 마감 임박(2일 전)으로 HTTPS 미적용.
> **현 운영 자세:** 본 제안의 **옵션 D(HTTP 유지 + 보상통제)** 를 사실상 채택. ML 호출은 평문 유지, 리스크 수용.
> **재개 조건:** v1 EOL(2026-06-30) 이후 v2 이전이 필요해지면 → 본 문서 **옵션 B**가 출발점.
> **연계:** [`info.md`](./info.md) §2·§4.4·§5, [`../achieve/design_backend.md`](../achieve/design_backend.md) §4(ML 추상화)
> **목적:** 현재 **HTTP 평문**으로 호출되는 ML 엔드포인트(`test4`, ACI/Designer classic)를
> Backend(App Service, HTTPS 적용됨)와 **암호화 채널(TLS)** 로 연동하는 방법을 공식 문서 기준으로 비교·권장.

---

## 0. 한 줄 결론 (TL;DR)

현재 모델은 **classic Designer + ACI(v1)** 산출물이라 *손쉬운 네이티브 HTTPS 경로가 없다.*
그리고 **Azure ML SDK/CLI v1은 2026-06-30 지원 종료**(오늘 기준 **약 1주 남음**)다.
→ **v1 ACI에 커스텀 인증서로 TLS를 붙이는 투자(옵션 A)는 권장하지 않으며**, 사실상 두 갈래다:

- **단기/현실적:** **옵션 D** — HTTP 유지 + 보상통제(키 회전·전송 데이터 최소화·리스크 명시 수용). 백엔드 변경 0.
- **정공법/권장:** **옵션 B** — 모델을 **v2 관리형 온라인 엔드포인트로 재배포**(HTTPS 기본, 인증서 관리 불필요). 일회성 재배포 비용.

어느 쪽이든 **백엔드 코드 구조는 그대로**(교체점은 `azure.py` 변환 2함수 + `.env`).

---

## 1. 현황 & 위협 모델

| 구간 | 프로토콜 | 현재 상태 |
|---|---|---|
| Client → Backend | **HTTPS** | App Service 기본 TLS 적용 ✅ |
| **Backend → ML** | **HTTP(평문)** | `http://7924e88e-…koreacentral.azurecontainer.io/score` ⚠️ |

- ML 호출 시 `Authorization: Bearer {key}` + 요청/응답 본문(전력 사용량 피처)이 **평문 전송**.
- 두 리소스 모두 **Azure Korea Central** 내부라, 트래픽은 대체로 Azure 백본을 경유한다.
  그러나 ACI 엔드포인트는 **공개 라우팅 가능(public FQDN)** 이며 평문이므로,
  경로상 도청·키 탈취 가능성을 **0으로 보긴 어렵다**(특히 키가 평문 노출 시 엔드포인트 무단 호출 위험).
- 데이터 민감도는 낮은 편(공개성 기상/사용량 피처)이나, **키 노출은 가용성·과금 리스크**로 직결.

> 따라서 핵심 보호 대상은 **데이터 기밀성**보다 **인증 키의 평문 노출 차단**.

---

## 2. 핵심 제약 (이 결정을 좌우하는 사실)

1. **모델이 classic Designer 산출물(`amlstudio-test4:1`) + ACI 배포(v1).**
   Studio "Web service" 배포 마법사는 Designer 모델에 대해 **AksCompute 또는 ACI** 만 대상으로 제공 —
   **관리형 온라인 엔드포인트(v2)를 마법사에서 직접 선택 불가.**
   (출처: *Use Studio to Deploy Models Trained in Designer*, v1)
2. **v1 수명 종료 임박.** SDK v1은 2025-03-31 deprecated, **지원 종료 2026-06-30**.
   *"Support for it will end on June 30, 2026."* → v1 ACI에 TLS를 새로 투자하는 건 **수명이 1주 남은 경로에 대한 투자**.
3. **ACI는 Microsoft 제공 인증서 자동화가 없다.** TLS를 붙이려면 **본인 소유 도메인 + CA 인증서**를 직접 준비·갱신해야 함(§3 옵션 A). AKS는 Microsoft 관리 인증서(`leaf_domain_label`) 자동 발급 가능.
4. **ACI IP 비고정.** ACI 공개 IP는 고정 보장이 없어, 커스텀 도메인 A레코드 매핑 방식이 **깨지기 쉬움**.
5. **v2 관리형 온라인 엔드포인트는 HTTPS가 기본.** `https://<endpoint>.<region>.inference.ml.azure.com/score`, **Microsoft 관리 TLS 인증서 자동·갱신 불필요.**

---

## 3. 옵션 비교

| | 옵션 A: ACI에 커스텀 TLS | 옵션 B: v2 관리형 온라인 엔드포인트 재배포 ⭐ | 옵션 C: AKS 재배포 | 옵션 D: HTTP 유지 + 보상통제 |
|---|---|---|---|---|
| **HTTPS 획득** | ✅ (직접 인증서) | ✅ **기본 제공** | ✅ (MS 인증서 가능) | ❌ (평문 유지) |
| **인증서 관리** | 본인(구매·갱신·DNS) | **불필요(MS 관리)** | MS 관리 or 본인 | 해당 없음 |
| **도메인 소유 필요** | **필요** | 불필요 | 불필요(leaf 도메인) | 불필요 |
| **v1/v2** | v1 (1주 후 EOL) | **v2(현행 지원)** | v1 legacy/ v2 가능 | v1 유지 |
| **재배포 필요** | 예(재배포) | 예(재구성) | 예(클러스터+재배포) | **아니오** |
| **월 비용 체감** | ACI 동일 + 도메인/인증서 | 소형 인스턴스 상시 1대 | **AKS 클러스터(최소 다중노드) → 높음** | 현행과 동일 |
| **백엔드 코드 영향** | `.env` URI만(http→https) | `.env` + 변환 2함수 재점검 | `.env` URI | 없음 |
| **난이도/소요** | 중(불안정) | **중(일회성)** | 높음(과투자) | **최저** |
| **소규모 5일 프로젝트 적합도** | 낮음 | **높음(정공법)** | 낮음 | 높음(단기) |

> ⭐ **권장:** 단기 운영 지속이면 **D**, 제대로 가져갈 거면 **B**. **A·C는 비권장**(A는 EOL 임박+불안정, C는 과투자).

---

## 4. 옵션별 상세

### 옵션 A — 기존 ACI에 커스텀 인증서로 TLS 적용 (❌ 비권장)
- **요구사항:** ① 본인 소유 도메인/FQDN, ② CA 발급 TLS 인증서(PEM, **풀체인+키**), ③ FQDN→ACI IP **DNS 매핑**, ④ 배포 설정에 `ssl_enabled=True`(인증서/키/cname) 지정해 **재배포**, ⑤ **연 1회 갱신**.
- **결정적 약점:** ACI **IP 비고정** → 매핑 파손 위험. 게다가 **v1 경로(1주 후 EOL)** 에 인증서 운영 부담을 새로 얹는 셈.
- **백엔드 영향:** `AZURE_ML_SCORING_URI` 를 `https://{내도메인}/score` 로 교체 — 코드 변경 거의 없음(payload 동일).
- **판단:** 기술적으로 가능하나 **투자 대비 수명·안정성이 최악**. 권장하지 않음.

### 옵션 B — v2 관리형 온라인 엔드포인트로 재배포 (⭐ 권장: 정공법)
- **왜:** **HTTPS 기본 + MS 관리 인증서(갱신 불필요) + 현행 지원(v2) + 오토스케일**. 인증서/도메인/DNS 부담 전무.
- **방법(개념, 코드 아님):** Designer가 생성한 **`score.py` + `conda_env.yaml` + 등록 모델**을 기반으로 v2 *managed online endpoint* 의 커스텀 배포로 재구성.
  - ⚠️ **검증 필요 리스크:** classic Designer 사전구성 컴포넌트는 관리형 온라인 엔드포인트에서 **그대로는 미지원**일 수 있음 → `score.py`가 의존하는 `azureml.studio/azureml.designer` 런타임이 v2 환경에서 동작하는지 **사전 PoC 필요**. (안 되면 추론 로직을 표준 scoring 스크립트로 경량 재작성.)
- **백엔드 영향:** `.env`의 URI/키 교체. **요청/응답 스키마가 Designer classic(`{"Inputs":{"input1":[…]}}` → `{"Results":{"WebServiceOutput0":[…]}}`)과 달라질 수 있으므로** `app/ml/azure.py`의 `_to_aml_payload`/`_from_aml_response` **2함수만** 재점검(설계상 격리 지점 — 라우터·서비스·스키마 불변). 단, score.py를 같은 계약으로 작성하면 변환부도 무수정 가능.
- **비용:** 관리형 엔드포인트는 **소형 인스턴스 1대 상시 과금**(ACI 0.1vCPU보다 상향). 소규모면 최저 SKU로 충분.
- **승인 경계:** Azure 리소스 **생성/재배포 → 사용자 승인 필수**(CLAUDE.md). 본 문서는 제안까지.

### 옵션 C — AKS로 재배포 (❌ 과투자)
- HTTPS는 Microsoft 관리 인증서(`leaf_domain_label`)로 자동화 가능하나, **AKS 클러스터 상시 비용·운영 부담**이 소규모 비영리/5일 프로젝트엔 과함. 제외.

### 옵션 D — HTTP 유지 + 보상통제 (✅ 단기 현실안)
- HTTPS를 당장 못/안 붙일 경우의 **리스크 완화**:
  1. **키 회전 주기 단축** + primary/secondary 이중키 운용(이미 `AZURE_ML_AUTH_PRI/SEC_KEY` 보유).
  2. **전송 데이터 최소화**(필수 8피처만; 이미 스키마 `extra="forbid"`).
  3. **App Insights 의존성 실패/이상 호출 알림**(이미 §7 구성)로 키 오·남용 조기 탐지.
  4. **info.md §4.4에 "평문 수용" 리스크를 명시적으로 문서화**(수용된 리스크임을 기록).
- 백엔드 변경 **0**. 단, 이는 **암호화가 아니라 리스크 수용**임을 분명히 할 것.

---

## 5. 권장안

1. **운영을 며칠~수주 더 현행대로 둘 거라면 → 옵션 D**(보상통제 + 리스크 문서화)로 충분. 가장 비용효율적.
2. **이 백엔드를 계속 유지·확장할 거라면 → 옵션 B**(v2 관리형 엔드포인트)로 **한 번에 정리**.
   v1 EOL(2026-06-30)을 감안하면 **어차피 v2 이전은 불가피** → HTTPS는 그 과정의 부산물로 자연 해결.
3. **옵션 A/C는 채택하지 않음**(수명·안정성/비용 사유).

> 즉, "HTTPS만을 위한 최소 작업"은 존재하지 않으며, **올바른 다음 단계는 v2 이전(B)** 이고
> 그 전까지의 **임시 안전판은 D**다.

---

## 6. 백엔드 측 영향 요약 (어느 옵션이든 작음)

- 교체점은 설계대로 **`app/ml/azure.py` 변환 2함수 + `.env`** 로 **격리**되어 있음 → 라우터/서비스/스키마 불변.
- 옵션 A/D: `.env`의 `AZURE_ML_SCORING_URI`만(또는 무변경).
- 옵션 B: `.env` URI/키 + (스키마 달라지면) 변환 2함수 재점검 + **테스트(`mock.py`/`test_predict`) 계약 동기화**.
- 공통 재발방지: `httpx`는 https 스킴이면 **인증서 검증 기본 활성** — 검증 비활성(`verify=False`) **금지**(MITM 무력화). 라이브 전 `/health`·`/api/v1/predict` 200 회귀 확인.

---

## 7. 열린 질문 / 필요 정보 (검토 시 알려주세요)

1. **운영 지속 기간:** 이 엔드포인트를 며칠 더 쓰고 끝인지(→D) vs 계속 유지·확장(→B)?
2. **재배포 권한/주체:** ML 워크스페이스 재배포를 이쪽에서 할 수 있는지(엔드포인트는 `김예찬`님 생성)? 팀 협의 필요 여부.
3. **비용 허용치:** v2 관리형 엔드포인트 **소형 인스턴스 상시 과금** 수용 가능 여부(비영리 예산).
4. **도메인 보유:** (옵션 A 검토 시에만) 팀이 소유한 도메인이 있는지 — 없으면 A는 사실상 탈락.
5. **데이터 민감도 재확인:** 전송 피처가 정말 비민감인지 — 민감하면 D의 "수용"이 부적절, B 강제.

---

## 8. 참고 (공식 문서)

- Secure web services using TLS (Azure ML, v1) — ACI 커스텀 인증서/AKS MS 인증서, PEM 풀체인, 연 갱신
  `https://learn.microsoft.com/azure/machine-learning/v1/how-to-secure-web-service`
- Use Studio to Deploy Models Trained in Designer (v1) — Designer 배포 대상=AksCompute/ACI, **SDK v1 지원 종료 2026-06-30**
  `https://learn.microsoft.com/azure/machine-learning/how-to-deploy-model-designer?view=azureml-api-1`
- Deploy ML models to online endpoints (v2) — 관리형 온라인 엔드포인트 = HTTPS 기본
  `https://learn.microsoft.com/azure/machine-learning/how-to-deploy-online-endpoints?view=azureml-api-2`
- Secure managed online endpoints (private endpoint/VNet, v2)
  `https://learn.microsoft.com/azure/machine-learning/how-to-secure-online-endpoint?view=azureml-api-2`
- Microsoft Q&A — Secure Azure ML REST endpoints deployed in ACI with TLS(커스텀 인증서·DNS·IP 비고정 경고)
  `https://learn.microsoft.com/answers/questions/318807/`
</content>
</invoke>

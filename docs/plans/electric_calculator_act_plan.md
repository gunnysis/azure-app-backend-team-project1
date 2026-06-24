# 개발 계획서 — ML 무반응(발견 C) 해소: `prev_year_usage` 신호 라우팅

> 문서 성격: 발견 C(라이브 ML이 에어컨 입력 무시)의 **근본 해결 개발 계획서** — **구현 설계 전 단계(방식·캘리브레이션 확정)**.
> 작성일: 2026-06-24 · 상태: **✅ 구현·배포·라이브검증 완료(발견 C 해소)** · 짝 문서: [`electric_calculator_act_checklist.md`](electric_calculator_act_checklist.md)(과제)
> 관련: [`../user_flow_review.md`](../user_flow_review.md) §6 발견 C, [`design_fallback_parity.md`](design_fallback_parity.md)(F4), 메모리 [[ml-model-ignores-current-usage]]
> 검증: 프로덕션 `/predict` 스윕 + **AML 워크스페이스 직접 데이터 포렌식**. 본 문서 수치는 전부 실측(보간 아님).

---

## 1. 배경 · 문제 정의

리포트의 예상 요금이 **에어컨 시간을 바꿔도 동일**(사용자 보고). 발견 C로 확정:

- 백엔드는 에어컨 습관을 `current_usage` 피처(132→600)로 합성해 ML에 전달하나, **라이브 모델이 `current_usage`를 완전히 무시** → `predicted_kwh` 상수(6월 141.07), `predicted == baseline` 항상 성립.

**근본 원인(§3-4 데이터 포렌식)**: `current_usage`는 입력 피처가 아니라 **학습 라벨(예측 타깃)**이다. 모델(Boosted Decision Tree)은 `current_usage`를 *나머지 피처로 예측*하므로 요청의 `current_usage`는 설계상 무시된다. 또한 **학습 데이터에 에어컨 변수가 전무** → **기존 데이터 재학습으로는 해결 불가**(에어컨↔사용량 라벨 수집은 MVP 범위 밖). 따라서 목표는 **모델이 실제로 반응하는 피처(`prev_year_usage`)에 에어컨 신호를 라우팅**해 무재학습으로 반영.

---

## 2. 현황 진단 (코드)

`app/services/feature_builder.py:estimate_usage()` — 현재 `prev_year_usage=132 상수`, `current_usage=clamp(132+aircon_kwh, 85, 650)`. 에어컨 신호가 흐르는 유일 피처가 `current_usage`인데 **그게 라벨이라 모델이 무시** → 신호 사장.

> 정정: 초기 체크리스트의 "`prev_year_usage`의 **null** 값을 채운다"는 부정확. 현재 prev는 null이 아니라 132 상수. 실제 작업은 *"상수 132를 사용량 유도값으로 교체"* + *"신호를 current→prev로 이동"*.

---

## 3. 검증 데이터 (실측 — 설계 근거)

### 3-1. 모델은 `prev_year_usage`에 강반응, `current_usage`는 무시
프로덕션 `/predict`, 6월 기상 고정:

| `prev_year_usage` | `current_usage` | `predicted` |
|---:|---:|---:|
| 76 | 132 | 92.69 |
| 132 | 132 | 141.07 |
| 300 | 132 | 287.29 |
| 600 | 132 | 402.47 |
| 132 | **600** | **141.07**(132행과 동일 → current 무시) |

### 3-2. `prev_year_usage` 전달함수 — 운영 구간 거의 항등, 400 초과 포화
6월 세밀 스윕: prev 85→95, 132→141, 200→200, 300→287, 350→328, **400→363**, 450→392, 600→402.
- **`prev∈[85,400]`: `predicted ≈ prev`**(약한 압축). → 합성 prev 값이 곧 최종 kWh.
- **`prev>400`: 급포화**(기울기 0.07) → 여기로 밀면 고시간대 "동일 요금" 재발 → **clamp 필수**.

### 3-3. 월 일반화 — 민감도 전 월 유지
8월: prev 132→167, 200→223, 300→309, 400→383(단조). 계절 floor만 이동(8월>6월). 설계가 전 월 일반화.

### 3-4. AML 데이터 포렌식 — 근본 원인 확증 (az CLI 직접 분석)
워크스페이스 `team_3_ML`(RG `project-1st-team-3`, koreacentral) 접근, 학습 CSV 다운로드·분석:

| 데이터셋 | 행수 | 컬럼 | 타깃(라벨) |
|---|---:|---|---|
| `final_max500.csv` | 36,428 | month_sin·cos, gu_code(=mapo 상수), **prev_year_usage**, avg_temperature, avg_humidity, total_rainfall, thi, `current_usage` | **`current_usage`(마지막 컬럼)** |
| `electricity_data_v4_no_outliers.csv` | 34,529 | 동일(gu_code 없음, avg_temp) | `current_usage` |
| `v5_with_usertype.csv` | 35,138 | +`user_type` | `current_usage` |

**라벨과의 상관(예측력)**:

| 피처 | 상관 → current_usage(라벨) |
|---|---:|
| **prev_year_usage** | **0.853** ← 압도적 단일 예측자 |
| user_type(v5) | 0.698 *(독립 신호 아님 — prev 등급 프록시: type1 prev≈114/type2 prev≈267)* |
| avg_humidity / thi / avg_temp | ~0.21 |
| total_rainfall | 0.13 |
| month_sin / month_cos | −0.21 / −0.08 |

**확증된 사실**:
1. **`current_usage`는 라벨**(예측 대상). 모델이 요청의 current_usage를 무시하는 건 **설계상 당연**(Designer 웹서비스 스키마가 라벨 컬럼까지 포함하지만 모델 미사용).
2. **`predicted ≈ prev_year_usage × ~0.85`**의 정체 = prev가 라벨의 압도적 예측자(연 사용량 자기상관). → **Approach A가 데이터로 검증됨**.
3. **에어컨/행동 변수 전무**. 라벨 ≈ prev + 기상 노이즈. → 기존 데이터 재학습으로 에어컨 반응 불가.
4. 라벨이 **max500·max379로 클립** → 모델 출력 ~400~500 포화(§3-2 재현). clamp 상한의 데이터 근거.

---

## 4. 설계 옵션 비교표

| 기준 | **A. 입력 라우팅** (✅ 확정) | **B. 출력 블렌딩** (백업) | C. ML 재학습 (범위 밖) |
|---|---|---|---|
| 동작 | 에어컨 추정→`prev_year_usage` 피처 주입, 모델이 변환 | 어댑터에서 `predicted=모델baseline+(추정current−추정baseline)` | 에어컨 피처 추가해 재학습 |
| ML 역할 | **루프 유지**(모델이 최종 산출) | 모델은 계절 floor만 | 정상화 |
| 수치 예측성 | 비선형(전달함수, 검증됨) | **선형·완전 제어** | 학습 의존 |
| 비교 UI 복원 | **자동**(prev차→predicted>baseline) | 자동(델타 가산) | 자동 |
| 상수 재사용 | **가능**(estimate_usage) | 가능 | 무관 |
| OOD/포화 | clamp 400으로 해소 | 없음 | 없음 |
| 구현 범위 | `feature_builder` 1곳 | `adapter` 1곳 | **AML 파이프라인+데이터수집** |
| 추가 과금 | **없음** | 없음 | **있음(컴퓨트·재배포)** |
| 실현성(현 데이터) | **즉시** | 즉시 | **불가**(에어컨 데이터 없음 → 수집 선행, MVP 밖) |
| 의미론 | prev에 올해 습관 주입(해킹) | "ML예측"=절반 휴리스틱 | 깨끗 |

**A vs B 본질**: 둘 다 "계절 floor=모델, 에어컨 델타=휴리스틱". A는 델타를 모델 입력(prev)으로 주입(§3-2로 `predicted≈prev`라 직관 제어·ML 루프 유지), B는 모델 출력에 직접 가산(완전 선형). **C는 현 데이터로 불가** — 별도 데이터 수집 장기 과제.

### ✅ 결정 — **방식 A(입력 라우팅) 확정**
**확정 근거**: ① §3 실측으로 메커니즘·반응대역·월일반화가 **검증된 유일한 방식**. ② **ML을 추론 루프에 유지**(B는 모델 출력을 사후 가산해 모델을 사실상 우회 — "ML 예측" 표기와 충돌). ③ baseline 비교가 **별도 코드 없이 자동 복원**(prev 차이가 곧 predicted 차이). ④ 변경 범위 최소(`feature_builder` 1곳, 어댑터·스키마 불변). ⑤ 기존 `estimate_usage` 상수 재사용으로 F4 정합 유지.
- **B(블렌딩)는 동등 후보로 보류**(기각 아님): A 운영 중 모델 전달함수가 불안정(재학습·교체)해지면 **즉시 전환 가능한 백업 설계**로 부록 §12에 보존. 전환 비용 낮음(어댑터 1곳).
- **C(재학습)는 범위 밖**: 에어컨 라벨 데이터 부재로 현재 불가. 데이터 확보 시 별도 안건.

---

## 5. 확정 설계 — A(입력 라우팅) + 듀티 보정 + clamp

### 5-1. 상수 (단일 진실원 — 백엔드 `feature_builder.py` ↔ 프론트 `script.js` 동기화)
| 상수 | 값 | 의미 / 근거 | 프론트 미러 |
|---|---|---|---|
| `AIRCON_DUTY_CYCLE` | **0.60** | 압축기 평균 가동률(물리) + 모델 반응대역 적합(§5-2 라이브 캘리브레이션) | `USAGE_DUTY_CYCLE` |
| `MODEL_PREV_MAX_KWH` | **400.0** | 모델 `prev_year_usage` 반응 상한(>400 포화, 라벨 클립 max500 근거 §3-2·3-4) | 폴백 표시 상한 미러 |
| `BASE_MONTHLY_KWH` | 132.0 | 기저(불변) | `USAGE_BASE_MONTHLY_KWH` |
| `USAGE_MIN/MAX_KWH` | 85 / 650 | 추정치 클램프(불변) | 동일 |

### 5-2. 함수 역할 (백엔드 로직 변경 = `feature_builder.py` 1파일, 프론트는 상수 미러만 §6)
**핵심**: 에어컨 추정 사용량을 `current_usage`(라벨, 무시됨)가 아니라 **모델이 반응하는 `prev_year_usage` 피처 슬롯에 싣는다.**

- `estimate_usage()` — 에어컨 기여분에 **`AIRCON_DUTY_CYCLE` 적용**(타입별 전력·배수 위에 곱). 반환:
  - `prev_year_usage` ← `clamp(132 + aircon_kwh, 85, MODEL_PREV_MAX_KWH)` *(모델 입력, 400 clamp)*
  - `current_usage` ← `clamp(132 + aircon_kwh, 85, 650)` *(라벨 슬롯·모델 무시. features_used echo·폴백 표시용)*
  - **docstring 갱신 필수**: prev가 더 이상 "작년 상수 132"가 아니라 "에어컨 보정 사용량(모델 핸들)"임을 명시(의미론 §7).
```python
aircon_kwh = hours * DAYS_PER_MONTH * power_kw * type_multiplier * AIRCON_DUTY_CYCLE
if 0 < hours <= 1: aircon_kwh += SHORT_RUN_BONUS_KWH      # 단시간 보정(기존)
usage = clamp(BASE_MONTHLY_KWH + aircon_kwh, USAGE_MIN_KWH, USAGE_MAX_KWH)
prev_year_feature = min(usage, MODEL_PREV_MAX_KWH)        # ← 모델 입력(반응 피처)
return round(prev_year_feature, 2), round(usage, 2)
```
- `build_features()` — 반환 첫값을 `prev_year_usage` 피처에, 둘째값을 `current_usage` 피처에 매핑(나머지 6피처 불변).
- **어댑터 무변경**: baseline 행(에어컨 0h)→ `prev=132`→ 모델 ~141 = `baseline_kwh`. 사용자 행→ `prev=132+델타`→ 더 큼. **`predicted>baseline` 자동 복원**(2행 배치·`predictions[0]/[1]` 추출 그대로).

### 5-3. 캘리브레이션 — **라이브 검증 확정**(듀티 0.60, unknown 타입, 6월)
프로덕션 `/predict`에 듀티 0.60이 만드는 `prev` 값을 그대로 투입해 측정한 **최종 예측 곡선**(보간 아님):

| 에어컨 h | 0 | 4 | 8 | 12 | 16 | 20 | 24 |
|---|---|---|---|---|---|---|---|
| `prev`(투입) | 132 | 179 | 226 | 272 | 319 | 366 | 400* |
| **predicted_kwh** | **141** | **184** | **220** | **259** | **313** | **350** | **363** |

`*` 24h는 412.8→clamp 400. **단조 증가·포화 평탄구간 없음**, 스프레드 **141→363(+222 kWh)**. → 사용자 보고("시간 바꿔도 동일") 해소. 타입별(fixed×1.1/inverter×0.92)은 동일 메커니즘으로 스케일.
> 듀티 0.60 채택 사유: ① 물리적 압축기 가동률(50~70%) 중앙. ② 모델 반응대역 `[132,400]`에 0~24h를 포화 없이 펼치는 유효 증분(~11.7 kWh/h on prev)을 만족(19.5/h였던 무보정은 12h에서 포화). 미세조정 여지는 있으나 본 값으로 확정.

---

## 6. 구현 변경점

| 파일 | 변경 | 비고 |
|---|---|---|
| `app/services/feature_builder.py` | `AIRCON_DUTY_CYCLE=0.60`·`MODEL_PREV_MAX_KWH=400` 추가, `estimate_usage` 듀티 적용+prev 라우팅(§5-2), docstring 갱신 | **유일 핵심 변경** |
| `app/api/v1/adapter.py` | **무변경** | 2행 배치·추출 그대로 |
| `azure-app-frontend/script.js` | `USAGE_DUTY_CYCLE=0.60` 동기화 + 폴백 400 상한 미러 | 승인 후 푸시=SWA 배포 |
| `app/data/...`·스키마 | **무변경** | 8피처 계약 불변 |
| 테스트 / parity_check | §8 (단위·라이브 스윕·민감도 가드·parity) | 재발방지 |

---

## 7. 영향 분석
- ✅ 비교 UI 복원(predicted>baseline).
- ⚠️ 폴백(F4) 재평가: 라이브 크기 변동(모델 압축+clamp) → 폴백에 동일 clamp 미러로 잔차 ≤수% 억제, parity_check에 반영.
- ⚠️ OOD: prev>400 학습분포 밖 → clamp가 OOD 가드.
- 📝 의미론: `prev_year_usage`가 "작년"이 아닌 "에어컨 보정 사용량" 운반 — 주석·API_CONTRACT 명시.

---

## 8. 테스트·검증
1. **단위(pytest)**: prev에 델타 반영·clamp 동작·경계(0/24h, ≤1h, 타입별).
2. **라이브 스윕 회귀**: 배포 후 `/estimate` hours 0→24 → `predicted` 단조 증가·predicted>baseline. *(발견 C가 "스윕 시 상수"였으므로 상시 스모크 편입.)*
3. **모델 민감도 가드**: `/predict` prev 132 vs 300 응답차 > 임계 — 모델 교체 회귀 조기탐지.
4. **폴백 parity**: parity_check에 clamp 추가.
5. **월 스폿체크**: 6·8월.

---

## 9. 롤백
`feature_builder` 순수함수 국소 변경 → `git revert` 1커밋. 어댑터·스키마 불변. 프론트 독립 revert(푸시=배포라 원복도 승인).

---

## 10. 재발방지
1. **포화 clamp 누락=버그 재발**: `MODEL_PREV_MAX_KWH` + 단조성 스윕 테스트(§8-2) 상시 가드.
2. **상수 3중 분기 방지**: 새 공식 발명 대신 `estimate_usage` 재사용 + 프론트 동기화(parity_check 탐지).
3. **모델 무반응/라벨혼동 조기탐지**: §8-3 민감도 가드 스모크 편입. 데이터 계약(어느 컬럼이 라벨인지) 문서화 — 재발 핵심.
4. **배포 비대칭**: 백엔드 수동배포 → 변경 후 `deploy.sh` + §8-2 라이브 검증(커밋≠배포).

---

## 11. 결정·진행 현황
- [x] **방식 확정**: ✅ **A(입력 라우팅)** — §4. B 백업(부록 §12), C 범위 밖.
- [x] **듀티 0.60 / clamp 400 확정**: ✅ §5-3 라이브 검증(0h→141, 24h→363, 단조).
- [x] **구현 완료(커밋)**: ✅ 백엔드 `feature_builder`(`15d1e84`) + 프론트 미러(`2b4b441`). 어댑터·스키마 불변.
- [x] **로컬 검증**: ✅ pytest 48 passed(회귀 4종 추가) · 프론트↔백엔드 정합 그리드 220케이스 0 불일치 · 백엔드 prev 곡선 = 라이브 /predict 검증값 일치.
- [x] **배포·라이브검증 완료**: ✅ 백엔드 `deploy.sh`(`RuntimeSuccessful`)·프론트 SWA(success). 라이브 `/estimate` 스윕 — predicted **141→157→184→205→220→259→313→350→363**(0~24h 단조)·baseline 141 고정(predicted>baseline 전구간). **사용자 보고 증상 해소 확정.**
- [ ] **장기(C)**: 에어컨↔사용량 라벨 데이터 수집 후 재학습 — 별도 안건.

---

## 12. 부록 — 백업 설계 B(출력 블렌딩) *(A 전환 대비, 미채택)*
모델 전달함수가 재학습·교체로 불안정해지면 어댑터 사후 보정으로 즉시 전환:
```
predicted = model_baseline + (추정current − 추정baseline)
# model_baseline = 에어컨 0h 행의 모델 출력(계절 floor), 추정* = estimate_usage(듀티 적용)
```
- 장점: 완전 선형·제어 용이, 모델 전달함수 비의존. 단점: "ML 예측"이 절반 휴리스틱(표기 정합 필요).
- 변경 범위: `adapter.estimate` 1곳(`feature_builder`는 추정식만 제공). 전환 비용 낮음.

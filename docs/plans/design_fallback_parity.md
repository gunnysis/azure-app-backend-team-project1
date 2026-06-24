# 구현 설계 — 프론트 폴백 정합(F4): `localMockPredict` ↔ 백엔드 `estimate_usage`

> 문서 성격: [`user_flow_review.md`](../user_flow_review.md) **F4**(프론트 폴백이 라이브 경로와 수치 불일치)의 구현 설계.
> 상태: **✅ 구현 완료 — 푸시(=SWA 배포) 대기**. 승인: ⓐ(권장)·Q2 yes·Q3 유지. 작성·구현: 2026-06-24.
> 근거: 양 레포 코드 정독 — 프론트 `azure-app-frontend/script.js`(`localMockPredict` L298-313, `buildPayload` L282-296, 상수 L1-13), 백엔드 `app/services/feature_builder.py`(`estimate_usage`).
> 결정 전제: F4는 사용자 자율 작업(프론트 `main` 수정·SWA 실배포 승인 불요). 단 본 설계는 **검토·승인 후 구현**.
>
> **🔄 후속(2026-06-24, 발견 C):** 본 F4 정합 계약은 이후 **발견 C 해소**로 확장됐다 — 정합 대상 상수에
> `USAGE_DUTY_CYCLE=0.60`·`MODEL_PREV_MAX_KWH=400`(에어컨 신호를 `prev_year_usage`로 라우팅 + 모델 포화 회피
> clamp)이 추가되어 양쪽에 미러됨. 본 문서 본문의 산식(아래)은 발견 C **이전** 스냅샷이며, 현행 정합 상수·근거는
> [`electric_calculator_act_plan.md`](electric_calculator_act_plan.md) 참조. F4의 "폴백=백엔드 추정식" 원칙은 유지.

---

## 0. 요약 (먼저 읽기)

- **문제:** 프론트 폴백 `localMockPredict()`는 사용자가 보낸 `aircon_power_w`·`aircon_type`을 **무시**하고 고정 `0.65kW`로 계산한다. 백엔드 라이브 경로(`feature_builder.estimate_usage`)는 **타입별 전력(760/560/650)·배수(1.1/0.92/1.0)** 를 반영한다. → 백엔드 장애로 폴백이 뜨면 사용자에게 보이는 kWh가 평소(라이브)와 최대 **~14% 어긋난다**(§3 표).
- **해결:** 백엔드 `estimate_usage`의 로직·상수를 프론트로 **1:1 포팅**(권장안 ⓐ). 이미 일치하는 항(base 132·30일·clamp 85~650·단시간 +8)은 유지.
- **정직한 한계(중요):** 폴백(휴리스틱)은 라이브(ML 출력 `Scored Labels`)와 **완전 일치 불가**. 폴백이 복제할 수 있는 건 모델 *입력*(`current_usage`=추정식)뿐이고, **모델 보정분([F3])은 오프라인 재현 불가**. 따라서 본 설계의 정합 목표는 **"폴백 = 백엔드 추정식과 정확 일치"**(라이브 ML 출력과의 잔차 = ML 델타, 불가피).
- **드리프트 방지:** 두 레포(백엔드 Python · 프론트 순수 JS·무빌드)는 상수 공유 모듈이 불가 → **양쪽 교차참조 주석 + 등가성 검증 스크립트 + `API_CONTRACT.md` 동기화 의무 명시**로 재발 방지.
- **범위 밖:** baseline(폴백은 165 고정 유지) · ML 모델의 오프라인 실행 · 폴백 시각적 표식(별도 UX).

---

## 1. 문제 정의 / 근본 원인

### 현재 프론트 (`script.js` L298-313)
```js
function localMockPredict(payload) {
  const hours = payload.aircon_hours_per_day || 0;
  const powerKw = hours > 0 ? 0.65 : 0;     // ← aircon_power_w·aircon_type 무시(고정)
  const baseKwh = 132;
  let kwh = baseKwh + hours * 30 * powerKw;
  if (hours > 0 && hours <= 1) kwh += 8;
  const predictedKwh = Math.round(clamp(kwh, 85, 650));
  return { predicted_kwh: predictedKwh, estimated_bill: calculateElectricBill(predictedKwh),
           baseline_kwh: BASELINE_KWH, baseline_bill: BASELINE_BILL, source: "sample" };
}
```

### 현재 백엔드 (`feature_builder.estimate_usage`)
```python
default_power = TYPE_DEFAULT_POWER_W.get(aircon_type, FALLBACK_POWER_W)   # 760/560/650/0, else 650
power_w = aircon_power_w or default_power or FALLBACK_POWER_W             # 사용자 실측 우선
power_kw = power_w / 1000.0
multiplier = TYPE_MULTIPLIER.get(aircon_type, 1.0)                        # 1.1/0.92/1.0/0.0
aircon_kwh = aircon_hours_per_day * DAYS_PER_MONTH * power_kw * multiplier
if 0 < aircon_hours_per_day <= 1: aircon_kwh += 8
current = _clamp(BASE_MONTHLY_KWH + aircon_kwh, USAGE_MIN_KWH, USAGE_MAX_KWH)  # 132, 85, 650
```

**근본 원인:** 프론트는 ① 사용자 입력 `aircon_power_w`를 안 읽고, ② 타입별 기본 전력 차등이 없고, ③ 타입 배수(`TYPE_MULTIPLIER`)가 없다. `feature_builder.py` 주석의 "프론트 `localMockPredict`와 정합"은 **현재 거짓**(base·일수·clamp·단시간만 우연히 일치).

---

## 2. 설계 목표 / 범위

| 구분 | 내용 |
|---|---|
| **In** | `localMockPredict`의 `predicted_kwh`를 백엔드 `estimate_usage(current)` 산식과 **정확히 일치**시킨다(타입별 전력·배수·사용자 실측 전력 반영). |
| **Out** | • `baseline_kwh` 폴백(165 고정 유지 — 백엔드 baseline은 model-based 계절값이라 오프라인 재현 불가, 별도 사안) • 폴백을 화면에 시각 표식(별도 UX 결정) • ML 모델 자체의 오프라인 실행(불가) |
| **목표 지표** | 동일 입력에 대해 `localMockPredict.predicted_kwh == round(백엔드 estimate_usage.current)` (정수 반올림 오차 ≤ 1kWh). 라이브 ML 출력과의 잔차는 ML 델타로 잔존(불가피·문서화). |

---

## 3. 정합 대상 — 상수·로직 대조

| 항목 | 백엔드 `feature_builder.py` | 현재 프론트 | 조치 |
|---|---|---|---|
| 기저 사용량 | `BASE_MONTHLY_KWH=132` | `baseKwh=132` | ✅ 동일(유지) |
| 일수 | `DAYS_PER_MONTH=30` | `30`(인라인) | ✅ 동일(상수화) |
| 타입별 기본전력 | `{fixed760, inverter560, unknown650, none0}` | ❌ 없음(0.65kW 고정) | 🔧 **추가** |
| 타입 배수 | `{fixed1.1, inverter0.92, unknown1.0, none0.0}` | ❌ 없음 | 🔧 **추가** |
| 폴백 전력 | `FALLBACK_POWER_W=650` | (암묵 650=0.65kW) | 🔧 상수화 |
| 사용자 실측 전력 | `power_w = aircon_power_w or default …` | ❌ 미사용 | 🔧 **반영** |
| 단시간 보정 | `+8 (0<h≤1)` | `+8 (0<h≤1)` | ✅ 동일(유지) |
| 클램프 | `85 ~ 650` | `clamp(…,85,650)` | ✅ 동일(유지) |

### 정합 효과(대표 입력 — 손계산)
| 입력 | 라이브/백엔드 | **신 폴백(정합)** | 구 폴백(현재) | 구 괴리 |
|---|---|---|---|---|
| 인버터·6h·전력 미입력 | 224.7 → **225** | **225** ✅ | 249 | +24 (+11%) |
| 정속·8h·전력 미입력 | 332.6 → **333** | **333** ✅ | 288 | −45 (−14%) |
| 인버터·5h·전력 1000W | 270.0 → **270** | **270** ✅ | 230 | −40 (−15%) |
| 잘모름·0.5h·전력 미입력 | 149.75 → **150** | **150** ✅ | 150 | 0(우연 일치) |

→ `unknown`(650W·×1.0)만 구 폴백과 우연히 같고, `fixed`/`inverter`/실측전력 입력에서 현저히 어긋난다.

---

## 4. 구현안

### ⓐ 권장 — 백엔드 산식 1:1 포팅 (`script.js`)

```js
// ⚠️ 동기화 필수: 아래 상수·산식은 azure-app-backend
//    app/services/feature_builder.py(estimate_usage)와 1:1 일치해야 한다.
//    한쪽을 바꾸면 반드시 다른 쪽도 함께 바꿀 것(폴백↔라이브 수치 정합).
const USAGE_BASE_MONTHLY_KWH = 132;            // BASE_MONTHLY_KWH
const USAGE_DAYS_PER_MONTH = 30;               // DAYS_PER_MONTH
const USAGE_TYPE_DEFAULT_POWER_W = { fixed: 760, inverter: 560, unknown: 650, none: 0 };
const USAGE_TYPE_MULTIPLIER     = { fixed: 1.1, inverter: 0.92, unknown: 1.0, none: 0.0 };
const USAGE_FALLBACK_POWER_W = 650;
const USAGE_MIN_KWH = 85;
const USAGE_MAX_KWH = 650;

// 백엔드 estimate_usage 의 current 산식 포팅(에어컨 기여분 추정).
function estimateUsageKwh(payload) {
  const hours = payload.aircon_hours_per_day || 0;
  const type = payload.aircon_type || "unknown";
  // .get(type, fallback) 등가: 미지 키 → ??(undefined만), none=0 은 정의값이라 유지.
  const defaultPower = USAGE_TYPE_DEFAULT_POWER_W[type] ?? USAGE_FALLBACK_POWER_W;
  // `or` 등가: aircon_power_w 가 null/0(falsy) → 기본전력, 그것도 0(none) → 폴백.
  const powerW = payload.aircon_power_w || defaultPower || USAGE_FALLBACK_POWER_W;
  const multiplier = USAGE_TYPE_MULTIPLIER[type] ?? 1.0;
  let airconKwh = hours * USAGE_DAYS_PER_MONTH * (powerW / 1000) * multiplier;
  if (hours > 0 && hours <= 1) airconKwh += 8;
  return clamp(USAGE_BASE_MONTHLY_KWH + airconKwh, USAGE_MIN_KWH, USAGE_MAX_KWH);
}

function localMockPredict(payload) {
  const predictedKwh = Math.round(estimateUsageKwh(payload));
  return {
    predicted_kwh: predictedKwh,
    estimated_bill: calculateElectricBill(predictedKwh),
    baseline_kwh: BASELINE_KWH,        // 범위 밖(165 고정 유지)
    baseline_bill: BASELINE_BILL,
    source: "sample",
  };
}
```

### ⓑ 대안 — 코드 미변경, 주석만 "근사 폴백"으로 정정
- `localMockPredict` 위에 "폴백은 타입·실측전력 미반영 **근사값**(장애 시 임시 표시용), 라이브와 다를 수 있음" 명시. `feature_builder.py`의 "정합" 주석도 "부분 정합(base·일수·clamp만)"으로 정정.
- **장점:** 변경 최소. **단점:** 실제 괴리(~14%)는 그대로. → **권장은 ⓐ**(사용자가 프론트를 직접 소유·정확도 개선 의도).

---

## 5. JS ↔ Python 의미 정합 주의 (포팅 정확성)

| Python | JS 등가 | 함정 |
|---|---|---|
| `D.get(type, fb)` | `D[type] ?? fb` | `??`는 `null`/`undefined`만 폴백 → 미지 키 OK. **`||`는 금지**(`none:0`을 0→fb로 잘못 덮음) |
| `a or b or c` (truthy) | `a \|\| b \|\| c` | 여기선 의도적 truthy-or(`aircon_power_w` 0/null→기본) → `\|\|`가 정답 |
| `0 < h <= 1` | `h > 0 && h <= 1` | 동일 |
| `round(x, 2)` 후 정수표시 | `Math.round(x)` | 폴백은 정수 표시 → 서브-kWh 반올림차 ≤1kWh(수용) |

→ **전력 기본값 룩업은 `??`, 전력 우선순위는 `||`** 로 서로 다른 연산자를 써야 백엔드와 정확히 같다. 이 차이를 §6 등가 검증으로 못박는다.

---

## 6. 정합 검증 (구현 시 수행)

> 이 환경엔 JS 런타임(`node`)이 없다(프론트 무빌드). 따라서 **백엔드 venv에서 Python 등가 스크립트**로 두 산식의 일치를 격자 입력으로 증명한다(실행 가능·재현).

1. **등가 검증 스크립트(scratchpad, 비커밋):** `feature_builder.estimate_usage`의 `current`와, ⓐ JS 산식을 Python으로 옮긴 함수를 동일 격자에서 비교 — `hours ∈ {0,0.5,1,3,6,12,24}` × `type ∈ {fixed,inverter,unknown,none}` × `power ∈ {None,560,1000,5000}`. **전 격자 `round` 일치(≤1kWh)** 를 assert. 불일치 0건이어야 통과.
2. **브라우저 스모크:** 로컬에서 백엔드를 끊고(또는 잘못된 base URL) 폴백 유도 → 같은 입력의 라이브(백엔드 정상) `predicted_kwh`와 폴백 값이 정수 일치하는지 콘솔(`source`)로 확인.
3. **회귀:** 기존 일치 케이스(`unknown`·단시간 +8·clamp 경계 85/650)가 깨지지 않는지 격자에 포함.

---

## 7. 드리프트 방지 (재발 차단)

- **양방향 교차참조 주석:** 프론트 상수 블록(위) ⇄ 백엔드 `feature_builder.py` 상단에 상호 파일 경로 명시("동기화 필수").
- **`API_CONTRACT.md` §6**에 "폴백 산식은 백엔드 `estimate_usage`와 동일 상수 — 한쪽 변경 시 양쪽·이 문서 동시 갱신" 1줄 추가.
- 공유 모듈은 **불가**(별도 레포·순수 JS·무빌드·무패키지매니저) → 위 관행 + §6 등가 스크립트(원할 때 재실행)로 보강. 잔존 드리프트 리스크는 수용.

---

## 8. 변경 파일 / 배포 영향

| 파일 | 변경 | 비고 |
|---|---|---|
| `azure-app-frontend/script.js` | `localMockPredict` 교체 + 상수/`estimateUsageKwh` 추가 | 핵심 |
| `azure-app-frontend/index.html` | `script.js?v=…` 캐시버스트 쿼리 bump | 프론트 CLAUDE.md 규칙 |
| `azure-app-frontend/API_CONTRACT.md` | §6 동기화 의무 1줄 | 문서 |
| `azure-app-backend/app/services/feature_builder.py` | "정합" 주석을 정확히(상호참조) 정정 | **동작 무변경**(주석만) |

- **배포 영향:** 프론트 `main` 푸시 = **SWA 실배포**(메모리 [frontend-push-triggers-swa-deploy]). F4는 사용자 자율 승인 범위 → 본 설계 승인 후 구현·푸시 가능. CSP·엔드포인트 URL 변경 없음(`connect-src` 무영향).
- **과금:** 없음(클라이언트 계산만, ML 호출·인프라 변경 없음).

---

## 9. 리스크

| # | 리스크 | 대응 |
|---|---|---|
| R1 | 두 레포 상수 재드리프트 | §7 교차참조 + §6 등가 스크립트. 잔존 리스크 수용 |
| R2 | `??` vs `\|\|` 오포팅으로 미세 불일치 | §5 규칙 + §6 전 격자 assert로 차단 |
| R3 | JS 런타임 부재로 자동 단위테스트 없음 | Python 등가 검증으로 대체(§6.1) + 브라우저 스모크(§6.2) |
| R4 | 캐시로 구 `script.js` 잔존 | `?v=` bump(§8) |

---

## 10. 잔존 한계 (설계상 수용)

- **폴백 ≠ 라이브(ML 델타):** 폴백은 백엔드 *추정식*(`current_usage`)만 복제 → 라이브 ML 출력(`Scored Labels`)과는 **모델 보정분만큼 차이**가 남는다([F3]). 이는 오프라인 재현 불가로 **불가피**하며, 폴백은 어디까지나 장애 시 graceful 표시값이다.
- **baseline 폴백 165 고정:** 백엔드 baseline은 model-based 계절값이라 오프라인 복제 불가 → 폴백은 165 유지(F4 범위 밖).

---

## 11. 작업 순서 (승인 후 실행)

1. `script.js` — 상수 블록 + `estimateUsageKwh` 추가, `localMockPredict` 교체(ⓐ).
2. 백엔드 venv에서 §6.1 등가 스크립트 작성·실행 → 전 격자 일치 확인(불일치 시 산식 교정).
3. `feature_builder.py` 주석 정정 + `API_CONTRACT.md` §6 1줄 + `index.html` `?v=` bump.
4. 브라우저 폴백 스모크(§6.2).
5. 프론트 `main` 커밋·푸시(= SWA 배포) — F4 자율 범위. 백엔드 주석은 별도 커밋(무동작).

---

## 12. 검토 요청 (승인 필요)

- **Q1.** 구현안 **ⓐ(산식 포팅, 권장)** vs **ⓑ(주석만 정정)** — 어느 쪽으로 진행할지?
- **Q2.** 백엔드 `feature_builder.py` **주석 1줄 정정**(동작 무변경)을 함께 포함해도 되는지? (F4는 프론트 작업이나 상호참조 주석은 백엔드도 살짝 건드림.)
- **Q3.** `baseline` 폴백(165 고정) 유지가 맞는지 — 본 설계는 **범위 밖**으로 두었음(이견 시 별도 항목으로).

> 결정(2026-06-24): Q1=ⓐ, Q2=yes, Q3=유지. 아래 §13 구현·검증 로그 참조.

---

## 13. 구현·검증 로그 (2026-06-24)

### 변경 적용
| 파일 | 변경 | 비고 |
|---|---|---|
| `azure-app-frontend/script.js` | `USAGE_*` 상수 블록 + `airconMarginalKwh()` + `estimateUsageKwh()` 추가, `localMockPredict` 교체 | ⓐ 포팅 |
| `azure-app-frontend/script.js` | `getTipCandidates`(L491)의 절감 kWh를 `airconMarginalKwh`로 통일 | ⬇ 추가 발견 |
| `azure-app-frontend/index.html` | `script.js?v=20260624-fallback-parity` bump | 캐시버스트 |
| `azure-app-frontend/API_CONTRACT.md` | §6 폴백 동기화 의무 추가 | 문서 |
| `azure-app-backend/app/services/feature_builder.py` | 상수 헤더 주석을 정확히(상호참조)·stale `baseKwh` 정정 | 동작 무변경 |

### 🔍 추가 발견(근본 원인 확장) — 절감 팁의 동일 안티패턴
- `getTipCandidates`도 `powerKw = (aircon_power_w || 650)/1000`(타입 배수·기본전력 무시)로 절감량을 계산해 **예측 모델과 내부 불일치**(예: 인버터 절감량 과대표시)였다. F4와 동일 근본 원인.
- **근본 해결**: 비례 전력항을 `airconMarginalKwh(hours, payload)` **단일 헬퍼로 추출**해 예측·절감팁이 같은 모델을 쓰도록 리팩토링 → 중복·드리프트 원천 차단. (단시간 +8·clamp·base는 예측 전용으로 헬퍼 밖 유지 — 절감 마진엔 부적용이 맞음.)

### 검증 (재발방지)
- **등가성 스크립트**(scratchpad `parity_check.py`, JS 런타임 부재 대체): ① `script.js`에서 `USAGE_*` 상수 **실제 추출** → 백엔드 7종 **전부 일치** ② 격자 `hours{0,0.5,1,1.5,3,6,12,24}×type{4}×power{None,0,560,650,1000,5000}`=**192건 전수 등가**(round-2, 불일치 0) → **PASS ✅**.
- **구문 안전**: `{}`·`()`·`[]` 균형 OK, 구 참조(`0.65`/`baseKwh`/`powerKw`) 0건.
- **백엔드 회귀**: `pytest` **44 passed**(주석 변경 무영향).
- 참고: `.5` 경계 5건에서 JS `Math.round`(상향) vs Python `round` 1kWh 표시차 — 폴백 정수표시 전용·라이브 미사용이라 무해.

### 라이브 실측 — ML 델타 규모(§10 한계 정량화)
- 2026-06-24 라이브: `current_usage=224.74` 입력 → ML `predicted_kwh ≈ 141~152`. 즉 폴백(≈225)과 라이브(≈141~152)는 **수십% 차이**(예상보다 큼). F4는 "폴백=백엔드 추정식" 목표를 달성했으나, 라이브 표시값은 ML 출력이라 폴백과 본질적으로 큰 차가 남는다(설계 §10 수용 한계, [user_flow_review.md] 발견 B로 정정 기록).
- ⚠️ 별개 운영 발견: **프로덕션 백엔드가 `baseline_kwh`+6s 예산 커밋(2603ad9) 미배포** — 본 설계 범위 밖이나 [user_flow_review.md] §6에 기록(백엔드 재배포는 승인 필요).
</content>

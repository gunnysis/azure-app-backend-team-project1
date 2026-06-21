# SPEC — API / 인터페이스 명세

> 문서 성격: **외부에서 본 동작 계약**(엔드포인트·스키마·에러). 요구 배경은 [PRD](PRD.md), 내부 구현은 [TRD](TRD.md) 참조.
> 버전: 0.1.0 · 최종 수정: 2026-06-21 · Base URL(로컬): `http://127.0.0.1:8000`

---

## 1. 공통 규약

| 항목 | 값 |
|---|---|
| 프로토콜 | HTTP/1.1, JSON (`Content-Type: application/json`) |
| 인증 | `X-API-Key: <키>` 헤더 (예측 API 한정, 헬스 제외) |
| 버전 | 경로 프리픽스 `/api/v1` |
| 추적 | 요청/응답 `X-Request-ID`(없으면 서버 생성, 있으면 승계) |
| 인코딩 | UTF-8 |

### 미들웨어 처리 순서(바깥→안쪽)
`RequestID → CORS → 라우팅`. RequestID가 가장 바깥이라 모든 로그·에러에 id가 부여된다.
(CORS는 `CORS_ORIGINS`가 설정된 경우에만 활성화.) RateLimit은 미들웨어가 아니라 `predict` **라우트 데코레이터 + `RateLimitExceeded` 핸들러**로 적용된다.

---

## 2. 엔드포인트 요약

| 메서드 | 경로 | 인증 | RateLimit | 설명 |
|---|---|---|---|---|
| GET | `/health` | ❌ | ❌ | Liveness(프로세스 생존) |
| GET | `/health/ready` | ❌ | ❌ | Readiness(ML 도달성 포함) |
| POST | `/api/v1/predict` | ✅ | ✅ | 예측 요청 |
| GET | `/docs` | ❌ | ❌ | Swagger UI |
| GET | `/openapi.json` | ❌ | ❌ | OpenAPI 스키마 |

---

## 3. 엔드포인트 상세

### 3.1 `GET /health` — Liveness

- **인증/RateLimit**: 없음 (App Service 플랫폼 프로브 통과용)
- **200 응답**:
  ```json
  { "status": "ok" }
  ```

### 3.2 `GET /health/ready` — Readiness

- **인증/RateLimit**: 없음
- **동작**: 활성 `MLClient.health()` 호출로 백엔드 도달성 확인.
- **200 응답**:
  ```json
  { "status": "ready", "ml": true }
  ```
  ML 비도달 시 `{"status":"degraded","ml":false}` (HTTP는 200, 상태는 본문으로 구분).

### 3.3 `POST /api/v1/predict` — 예측

- **인증**: `X-API-Key` 필수.
- **RateLimit**: 기본 `60/minute`(IP 기준, 근사). 초과 시 429.
- **요청 본문** (`PredictRequest`, `extra="forbid"` — 정의되지 않은 필드 거부):

  | 필드 | 타입 | 필수 | 설명 |
  |---|---|---|---|
  | `inputs` | `list[float]` 또는 `dict[str, any]` | ✅ | 모델 입력. 실제 스키마 확정 시 구체화 |

  ```json
  { "inputs": [1, 2, 3] }
  ```
  또는
  ```json
  { "inputs": { "feature_a": 0.5, "feature_b": 12 } }
  ```

- **200 응답** (`PredictResponse`):

  | 필드 | 타입 | 설명 |
  |---|---|---|
  | `predictions` | `list[any]` | 모델 예측 결과 |
  | `model_version` | `string \| null` | 모델 버전(Mock: `"mock-1.0"`) |
  | `elapsed_ms` | `float` | 서버 측 처리 시간(ms) |

  ```json
  {
    "predictions": [0.83074],
    "model_version": "mock-1.0",
    "elapsed_ms": 0.42
  }
  ```

- **Mock 동작**: `inputs`의 sha256 해시 기반 **결정적** 점수(같은 입력 → 같은 출력). 실제 엔드포인트 없이 재현 가능한 테스트 제공.

---

## 4. 표준 에러 응답

모든 에러는 동일 포맷으로 반환된다.

```json
{
  "error": {
    "code": "ML_UNAVAILABLE",
    "message": "ML endpoint is temporarily unavailable.",
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "detail": null
  }
}
```

| HTTP | code | 발생 조건 |
|---|---|---|
| 401 | `AUTH_INVALID` | `X-API-Key` 누락/불일치 |
| 422 | `VALIDATION_ERROR` | 스키마 위반(누락 필드, 알 수 없는 필드, 타입 오류). `detail`에 안전한 검증 정보 |
| 429 | `RATE_LIMITED` | Rate limit 초과 |
| 404 | `HTTP_ERROR` | 미존재 경로 |
| 502 | `ML_UNAVAILABLE` | ML 엔드포인트 도달 실패(재시도 소진) |
| 502 | `UPSTREAM_ERROR` | ML 엔드포인트가 에러 응답(4xx 등) |
| 504 | `ML_TIMEOUT` | ML 엔드포인트 응답 타임아웃 |
| 500 | `INTERNAL_ERROR` | 미처리 예외(내부 메시지·스택 비노출) |

> 내부 예외 메시지·스택은 클라이언트에 노출하지 않고 로그에만 기록한다. `detail`은 검증 오류 등 안전한 정보로 제한.

---

## 5. 예시 (curl)

```bash
# 헬스
curl http://127.0.0.1:8000/health

# 예측(성공)
curl -X POST http://127.0.0.1:8000/api/v1/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: local-dev-key" \
  -d '{"inputs":[1,2,3]}'

# 인증 실패(401)
curl -X POST http://127.0.0.1:8000/api/v1/predict \
  -H "Content-Type: application/json" \
  -d '{"inputs":[1,2,3]}'

# 검증 실패(422) — 알 수 없는 필드
curl -X POST http://127.0.0.1:8000/api/v1/predict \
  -H "Content-Type: application/json" -H "X-API-Key: local-dev-key" \
  -d '{"inputs":[1,2,3],"unknown":1}'
```

---

## 6. 버전 / 호환성 정책

- 경로 버전(`/api/v1`)으로 호환성 경계 관리. 파괴적 변경은 `/api/v2`로 분기.
- 응답 필드 **추가**는 하위호환(클라이언트는 모르는 필드 무시 권장). 필드 **삭제/의미변경**은 버전 상향.
- 실제 ML 스키마 확정 시 `inputs`/`predictions` 구체화 — SPEC을 함께 개정한다.

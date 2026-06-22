# PRD — ML 연동 백엔드 (Product Requirements Document)

> 문서 성격: **제품 요구사항**(왜/무엇을). 기술 구현(어떻게)은 [TRD](TRD.md), 인터페이스 명세는 [SPEC](SPEC.md), 아키텍처 상세는 [design_backend.md](achieve/design_backend.md) 참조.
> 버전: 0.1.0 · 최종 수정: 2026-06-21 · 상태: 초기 베이스라인

---

## 1. 개요

Azure ML 엔드포인트를 외부 클라이언트에 안전하게 중계하는 **FastAPI 백엔드(BFF + 내부 라우팅 게이트웨이)**. 소규모 비영리 프로젝트로, 5일 개발 기간 내 운영 가능한 최소 인프라를 목표로 한다.

- **한 줄 정의**: 클라이언트 ↔ (본 백엔드) ↔ Azure ML Managed Online Endpoint 를 잇는 인증·검증·에러표준화 게이트웨이.
- **현재 단계**: ML 추상화 레이어 + Mock 구현으로 전 구간 동작·테스트 완료. 실제 ML 엔드포인트 연동은 정보 확보 후 진행(승인 필요).

## 2. 배경 / 문제 정의

- ML 모델은 Azure ML에 호스팅되나, **엔드포인트를 클라이언트에 직접 노출하면** 인증·CORS·요청검증·에러포맷·레이트리밋을 각 클라이언트가 떠안아야 하고 키가 외부로 새어나간다.
- 엔드포인트의 **실제 호출 규약·입출력 스키마가 아직 미확정**이라, 정보가 확정될 때까지 개발이 막히면 5일 일정을 맞출 수 없다.
- → 백엔드가 **단일 진입점**으로 횡단 관심사를 흡수하고, ML 호출부를 **추상화 레이어**로 격리해 실제 정보 없이도 파이프라인을 완성한다.

## 3. 목표 (Goals)

| # | 목표 | 측정 기준 |
|---|---|---|
| G1 | ML 호출을 단일 인터페이스 뒤로 격리 | `MLClient` ABC 1개, 구현체 교체는 `ML_CLIENT` 환경변수만 |
| G2 | 실제 엔드포인트 없이 전 구간 동작·테스트 | Mock으로 E2E 테스트 통과(현재 11건) |
| G3 | 횡단 관심사 표준화 | 인증/CORS/RateLimit/에러포맷/요청추적 일괄 적용 |
| G4 | Azure App Service(Code) 배포 준비 | startup.sh + 핀 고정 의존성 + App Settings 주입 설계 |
| G5 | 실제 ML 연동 시 변경 최소화 | `azure.py` 변환 함수 2개 + `.env`만 수정 |

## 4. 비목표 (Non-Goals)

- 사용자 로그인/세션, GitHub Easy Auth (참고 정보만 보유, 이번 범위 외)
- Azure API Management(APIM), 별도 Mock 서버/Mock API
- 데이터베이스, 영속 저장소, 사용자 관리
- 모델 학습·서빙 자체(ML 측 책임), 모델 버전 관리 UI
- 전역 정밀 Rate limit(Redis 공유 스토리지) — 향후 과제

## 5. 사용자 / 이해관계자

| 역할 | 관심사 |
|---|---|
| 프론트엔드/클라이언트 개발자 | 안정적인 예측 API, 일관된 에러 포맷, 명확한 스키마 |
| 백엔드 운영자(본 팀) | 배포 용이성, 시크릿 안전, 장애 추적성(request_id) |
| ML 담당자 | 엔드포인트 호출 규약·스키마 확정 후 연동 |

## 6. 핵심 요구사항 (우선순위)

### Must (필수)
- **R1** 예측 API: 인증된 요청을 받아 ML 결과를 프론트 친화적 형태로 반환.
- **R2** API Key 인증: `X-API-Key` 헤더, 상수시간 비교. 실패 시 401 표준 에러.
- **R3** 요청/응답 검증: Pydantic v2, 알 수 없는 필드 거부(`extra="forbid"`).
- **R4** 표준 에러 응답: `{error:{code,message,request_id,detail}}` 통일 포맷.
- **R5** 헬스체크: `/health`(liveness, 무인증), `/health/ready`(ML 도달성 포함).
- **R6** ML 추상화: `ML_CLIENT=mock|azure` 스위칭. 실제 정보 없이 동작.
- **R7** 시크릿 비커밋: `.env`/App Settings 주입, `.gitignore` 보장.

### Should (권장)
- **R8** Rate limiting(근사 보호): IP 기준, `X-Forwarded-For` 인지. 한계 문서화.
- **R9** 요청 추적: `X-Request-ID` 생성/승계, 응답 헤더·로그 기록.
- **R10** CORS: `CORS_ORIGINS` 환경변수 기반 허용 출처.

### Could (선택)
- **R11** 재시도/백오프(멱등 가정), 타임아웃 분리(connect/read).

### Won't (이번 제외)
- Redis 기반 전역 레이트리밋, 사용자 인증, APIM.

## 7. 성공 기준 (Acceptance)

- Mock 모드에서 `/api/v1/predict`가 결정적 결과 반환, 11개 테스트 그린.
- 인증 실패(401)/검증 실패(422)/레이트초과(429)/ML 장애(502·504) 모두 표준 포맷.
- gunicorn 멀티워커로 로컬 구동 시 워커별 lifespan 1회·동작 일관.
- 실제 ML 연동이 `azure.py` 변환 2함수 + `.env`만으로 가능(설계상 검증).

## 8. 제약 / 가정

- **일정**: 5일, 소규모 비영리 → 오버엔지니어링 지양.
- **런타임**: Python 3.14, FastAPI, Azure App Service Linux(**Code 배포**, Docker 아님).
- **플랜**: P0v3(Premium v3), **오토스케일 전제** → stateless 유지(인메모리 상태 의존 금지).
- **ML 규약**: `POST {scoring_uri}` + `Authorization: Bearer {key}`(authMode=key 기준). 입출력 스키마 미확정.

## 9. 위험 / 완화

| 위험 | 영향 | 완화 |
|---|---|---|
| ML 엔드포인트 정보 지연 | 연동 지연 | 추상화+Mock으로 본체 선완성, 연동은 변환 2함수로 국소화 |
| 인메모리 레이트리밋 부정확(멀티 인스턴스) | 보호 약화 | "근사 보호"로 문서화, 필요 시 Redis 전환(향후) |
| 시크릿 유출 | 보안 사고 | `.env` 비커밋, App Settings 주입, gitignore 검증 |
| 워커 행(hang) | 가용성 저하 | httpx 타임아웃 < gunicorn `--timeout` |

## 10. 마일스톤

| 단계 | 내용 | 상태 |
|---|---|---|
| M1 | 설계 문서 승인 | ✅ |
| M2 | 추상화+스키마+라우터+미들웨어+에러 | ✅ |
| M3 | 테스트·로컬 구동 검증 | ✅ |
| M4 | 실제 ML 연동(`AzureMLClient`) | ⏳ 정보 대기 |
| M5 | App Service 배포 | ⏳ **승인 필요** |

## 11. 미해결 질문

- 실제 ML 입력 스키마(필드명·타입)와 출력 형태?
- authMode가 key인지 AMLToken/AADToken인지?
- 예상 트래픽/동시성(워커 수·플랜 튜닝 근거)?

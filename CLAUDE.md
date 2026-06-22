# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

ML 연동 FastAPI 백엔드 (소규모 비영리, 개발기간 5일). Azure App Service 배포.
클라이언트 ↔ (본 백엔드 = BFF/게이트웨이) ↔ Azure ML Managed/Designer 엔드포인트.

## 작업 원칙
- **사전 절차**: 연구 → 점검 → 분석 → 설계 → 문서화 → (사용자 검토·승인) → 실행.
- **팩트체크**: 공식 문서 우선, 추측 금지. 불확실하면 검증 후 진행.
- **에러 해결**: 증상 봉합이 아닌 근본 원인 분석 후 해결. 근거를 보고에 기록.
- **품질**: 리팩토링·성능·테스트·디버깅·설계를 다양한 관점에서 검토.

## 자율 / 승인 경계
- **자율 진행**(승인 불필요): 코드 작성, 의존성 설치, 로컬 테스트, 설정 파일 생성·수정, push.
- **승인 필수**(실행 전 보고·대기): Azure 리소스 생성/변경, 실제 배포, 과금 발생 작업.

## 시크릿 / 버전관리
- 모든 키·시크릿은 `.env`로 관리, **절대 커밋 금지**. Azure 배포 시 App Settings로 주입.
- `.gitignore`에 `.env`, `.venv`, `__pycache__`, `*.zip` 포함(확인 완료).
- 설정 검증 시 실제 `.env` 로드 금지(시크릿 출력 위험) — 임시 env 변수로 검증.
- 의미 단위 커밋.

## 명령어
```bash
# 환경 구성
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt        # 런타임 + pytest
cp .env.example .env                         # API_KEY 등 값 채우기

# 로컬 실행 (Swagger: http://127.0.0.1:8000/docs)
uvicorn app.main:app --reload

# 테스트
pytest                                       # 전체
pytest tests/test_predict.py                 # 파일 단위
pytest tests/test_predict.py::test_predict_ok -v   # 단일 테스트
```
- `pytest.ini`: `asyncio_mode=auto` → `async def test_*` 에 데코레이터 불필요.
- 런타임 의존성은 `requirements.txt`에 전이 의존성까지 전부 핀 고정. 개발 전용은 `requirements-dev.txt`.

## 아키텍처 (상세: docs/achieve/design_backend.md, docs/TRD.md)

**요청 흐름**: 라우터(`app/api/v1`) → 의존성 주입(`app/api/deps.py`) → 서비스/BFF(`app/services`) → `MLClient` 추상화(`app/ml`) → Azure ML.

- **앱 조립**: `app/main.py:create_app()`. `lifespan`이 **워커당 1회** ML 클라이언트를 생성해 `app.state.ml_client`에 보관(커넥션 풀 재사용) → `deps.get_ml_client`가 재사용. 미들웨어는 나중에 추가한 것이 바깥 → `RequestContextMiddleware`가 가장 바깥에서 `request_id` 발급.
- **ML 추상화 = 핵심 교체점**: `app/ml/base.py`의 `MLClient`(ABC)가 유일한 접점. `ML_CLIENT=mock|azure`로 `factory.create_ml_client`가 구현체 선택(azure는 httpx 지연 import). **실제 연동 시 수정 범위는 단 2곳**: `app/ml/azure.py`의 `_to_aml_payload`/`_from_aml_response` 변환 함수 + `.env`. 라우터·서비스·스키마는 불변.
- **스키마 계약**: `app/schemas/prediction.py`. `PredictRequest.inputs`는 행(dict) 배열(`extra="forbid"`). 피처를 코드에 못박지 않음(모델 교체 내성). `azure.py`가 Designer 형식(`{"Inputs":{"input1":[...]}}`)으로 감쌈.
- **인증**: `deps.verify_api_key` — `X-API-Key` 헤더를 `secrets.compare_digest`로 상수시간 비교. `/health`는 인증·rate limit 제외.
- **에러 표준화**: 비즈니스 코드는 HTTP 상태를 다루지 않고 `app/core/errors.py`의 `AppError` 하위 예외를 raise. `app/core/exception_handlers.py`가 전역 핸들러로 `{"error":{code,message,request_id,detail}}` 단일 포맷 변환. 내부 메시지·스택은 클라이언트 미노출(로그만).
- **업스트림 호출 정책**(`azure.py`): 4xx 즉시 전달(재시도 무의미), 5xx·타임아웃은 지수 백오프 재시도(`ml_max_retries`). 타임아웃→504(`ML_TIMEOUT`), 그 외→502(`ML_UNAVAILABLE`/`UPSTREAM_ERROR`).
- **설정**: `app/config.py` pydantic-settings, `get_settings()`는 `lru_cache`로 프로세스당 1회 로드. 테스트는 `tests/conftest.py`가 **import 전에** env를 세팅하고(캐시 때문) ASGITransport는 lifespan 미실행이라 `ml_client`를 수동 주입.

## 운영 제약
- 배포: App Service **Code 방식**(Docker 아님), Oryx 빌드. startup은 `startup.sh`의 gunicorn+UvicornWorker.
- P0v3(Premium v3) **오토스케일 전제** → **stateless 유지**(인메모리 상태 의존 금지). slowapi rate limit은 인메모리라 멀티워커/멀티인스턴스에서 부정확(근사 보호). 정밀 제한 필요 시 Redis 백엔드로 교체.

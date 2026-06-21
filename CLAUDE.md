# CLAUDE.md — 프로젝트 작업 지침

ML 연동 FastAPI 백엔드 (소규모 비영리, 개발기간 5일). Azure App Service 배포.

## 작업 원칙
- **사전 절차**: 연구 → 점검 → 분석 → 설계 → 문서화 → (사용자 검토·승인) → 실행.
- **팩트체크**: 공식 문서 우선, 추측 금지. 불확실하면 검증 후 진행.
- **에러 해결**: 증상 봉합이 아닌 근본 원인 분석 후 해결. 근거를 보고에 기록.
- **품질**: 리팩토링·성능·테스트·디버깅·설계를 다양한 관점에서 검토.

## 자율 / 승인 경계
- **자율 진행**(승인 불필요): 코드 작성, 의존성 설치, 로컬 테스트, 설정 파일 생성·수정.
- **승인 필수**(실행 전 보고·대기): Azure 리소스 생성/변경, 실제 배포, 과금 발생 작업.

## 시크릿 / 버전관리
- 모든 키·시크릿은 `.env`로 관리, **절대 커밋 금지**. Azure 배포 시 App Settings로 주입.
- `.gitignore`에 `.env`, `.venv`, `__pycache__`, `*.zip` 포함(확인 완료).
- 의미 단위 커밋. push는 자율.

## 환경
- WSL(Ubuntu 24) / Python 3.14 / FastAPI / VS Code.
- 가상환경: `.venv`. 런타임 의존성 `requirements.txt`, 개발 `requirements-dev.txt`.
- 실행: `uvicorn app.main:app --reload` / 테스트: `pytest`.

## 핵심 설계 (상세: docs/design_backend.md)
- 계층: 라우터 → 서비스(BFF) → `MLClient`(추상화) → Azure ML.
- ML 구현체 전환: `ML_CLIENT=mock|azure`. 실제 연동은 `app/ml/azure.py` 변환 함수 2개 + `.env`만 수정.
- 인증: `X-API-Key` 헤더(상수시간 비교). 에러는 표준 포맷(`request_id` 포함).
- 배포: App Service **Code 방식**(Docker 아님), startup은 gunicorn+UvicornWorker.
- 운영: P0v3(Premium v3), **오토스케일 전제** → stateless 유지(인메모리 상태 의존 금지).

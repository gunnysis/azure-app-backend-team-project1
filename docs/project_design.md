# Claude Code 작업 지시서: ML 연동 백엔드 인프라 설정

## 프로젝트 개요
- **성격**: 소규모 비영리 프로젝트 (개발기간 5일)
- **목표**: Azure ML 엔드포인트 연동용 FastAPI 백엔드 인프라 설정
- **ML 연동**: Azure Machine Learning (엔드포인트 호출 방식 미확정 → 설계 단계에서 확정)
- **클라우드**: Azure App Service
- **루트 경로**: /mnt/c/Users/EL066/sesac/first_project_3team/azure-app-backend
- **FastAPI**: 초기 설정 완료 상태

---

## 작업 원칙 (모든 작업에 공통 적용)

### 일하는 방식
- **사전 절차**: 모든 작업 전 연구 → 점검 → 분석 → 설계 → 문서화. 문서를 내가 검토·승인한 뒤 자율 판단으로 실행한다.
- **팩트체크**: 공식 문서 우선, 외부 문서 보조. 추측 금지. 불확실하면 검증 후 진행.
- **에러 해결**: 증상 임시 봉합이 아닌 근본 원인 분석 후 해결. 해결 과정과 근거를 최종 보고에 기록.
- **품질 관점**: 리팩토링·성능·테스트·디버깅·설계를 항상 다양한 관점에서 검토하고, 판단 근거를 보고에 남긴다.

### 버전 관리 / 시크릿 관리
- **버전 관리**: 의미 단위로 커밋, 메시지에 작업 내용 명확히 기술. push는 자율 진행.
- **시크릿 관리**: 모든 키·시크릿은 `.env`로 관리, **절대 커밋 금지**. `.gitignore`에 `.env`, `.venv`, `__pycache__` 포함 확인. Azure 배포 시 시크릿은 App Settings로 주입.

### 자율 / 승인 경계
- **자율 진행** (승인 불필요): 코드 작성, 의존성 설치, 로컬 테스트, 설정 파일 생성·수정
- **승인 필수** (실행 전 반드시 보고·대기): Azure 리소스 생성/변경, 실제 배포, 과금이 발생하는 모든 작업

---

## 작업 목록

### 0. Claude Code CLI 설치 및 프로젝트 최적화 설정
- 루트 폴더(azure-app-backend)에 프로젝트 맞춤 Claude Code 환경 구성
- CLAUDE.md에 위 작업 원칙·자율/승인 경계·프로젝트 컨텍스트 기록
- 작업 시작 전 프로젝트 구조 분석 및 설계 문서 작성 → 검토 요청

### 1. API 게이트웨이 기능
- **설계 방향**: FastAPI 내부 라우팅 + BFF 레이어 (별도 APIM 미사용)
- 그 외 세부 설계(인증·CORS·Rate limiting·ML 프록시 방식 등)는
  공식/외부 문서 조사 + 프로젝트 분석 + 팩트체크 후 추천안을 자율 판단으로 설계

### 2. 데이터 유효성 검사
- Pydantic 기반 요청/응답 스키마 정의

### 3. 로컬 테스트 및 에러 핸들링
- 로컬 구동 검증
- 전역 예외 핸들러 및 에러 응답 표준화

### 4. 필요한 설정 작업
- 내가 제공해야 할 또는 궁금한 정보는 물어볼 것
- 환경변수, 의존성, 실행 설정 등 운영 전 준비

### 5. App Service 사전 배포
- ⚠️ **승인 필수 단계** — 배포 전 계획 보고 후 대기
- 배포 방식(ZIP deploy 등) 설계 단계에서 확정

---

## 개발 환경
- **OS**: Windows 11 Home
- **실행 환경**: WSL (Ubuntu 24 LTS)
- **언어**: Python 3.14
- **프레임워크**: FastAPI
- **IDE**: VS Code
- **루트 경로**: /mnt/c/Users/EL066/sesac/first_project_3team/azure-app-backend
- **코드 관리**: GitHub (설치 및 연결 완료)
  - git version 2.43
  - repo: https://github.com/gunnysis/azure-app-backend-team-project1.git

---

## 운영 환경
- **서비스**: Azure App Service (Linux, Python 3.14, FastAPI)
  - ✅ Python 3.14 런타임 지원 확인 완료
- **배포 도구**: Azure CLI
- **Resource Group**: project-1st-team-3
- **ML Backend Instance**
  - Product: Web App
  - Plan: ASP-project1stteam3-8d76 (P0v3: 1)
  - Name: app-mlbackend-prod-kc-01
  - Domain: app-mlbackend-prod-kc-01-h4a6byekfzhkcday.koreacentral-01.azurewebsites.net

---

## 참고 정보 (현재 미사용 — 향후 필요 시 활용)

### GitHub OAuth App (Azure Easy Auth용)
- **용도**: 배포된 웹앱에 GitHub 로그인 인증(Azure App Service Authentication / Easy Auth)을 붙일 때 사용
- **현재 상태**: 생성만 완료, **이번 작업에서는 사용하지 않음**
- **적용 판단**: ML 백엔드가 API 서버 성격이면 불필요. 사용자 로그인 기능이 실제로 필요해질 때 재검토
- Application name: azure-app-backend-3team
- URL: https://app-mlbackend-prod-kc-01-h4a6byekfzhkcday.koreacentral-01.azurewebsites.net
- Callback URL: .../.auth/login/github/callback
- Client ID: (GitHub OAuth App 설정 참조)
- Client Secret: `.env` 의 `oauth_client_secret_key` 변수
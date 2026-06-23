# azure-app-backend-team-project1

Azure ML 엔드포인트 연동용 **FastAPI 백엔드** (BFF + 내부 라우팅 게이트웨이).
클라이언트 ↔ (본 백엔드) ↔ Azure ML Managed Online Endpoint 사이에서 인증·검증·에러표준화·요청추적을 담당합니다.

- **런타임**: Python 3.14 / FastAPI
- **배포**: Azure App Service (Linux, **Code 배포** — Docker 아님)
- **상태**: **운영 배포 완료** — App Service에서 `ML_CLIENT=azure`로 실 ML 엔드포인트 E2E 동작(`/health`·`/api/v1/predict` 200). 23 tests green.

> ⚠️ Azure 리소스 생성/변경·실제 배포·과금 작업은 **승인 후** 진행합니다([CLAUDE.md](CLAUDE.md) 참조).

## 문서 맵

| 문서 | 내용 |
|---|---|
| [docs/PRD.md](docs/PRD.md) | 제품 요구사항 — 왜/무엇을 |
| [docs/SPEC.md](docs/SPEC.md) | API·인터페이스 명세 — 외부 계약 |
| [docs/TRD.md](docs/TRD.md) | 기술 구현 — 스택·구조·결정 근거 |
| [docs/achieve/design_backend.md](docs/achieve/design_backend.md) | 아키텍처 상세·팩트체크 출처 (아카이브) |
| [CHANGELOG.md](CHANGELOG.md) | 버전별 변경 이력 |
| [CLAUDE.md](CLAUDE.md) | 작업 원칙·자율/승인 경계 |

## 구조

```
app/
├── main.py            # FastAPI 앱(create_app, lifespan)
├── config.py          # 설정(pydantic-settings, .env)
├── api/               # 라우터 + 의존성(인증/주입)
│   ├── deps.py
│   └── v1/{health,predict}.py
├── schemas/           # Pydantic 요청/응답·에러 스키마
├── services/          # BFF 비즈니스 로직
├── ml/                # ML 추상화: base(ABC) / mock / azure / factory
└── core/              # errors / middleware / exception_handlers / ratelimit
```

ML 호출은 `MLClient` 인터페이스 뒤로 격리됩니다. `ML_CLIENT=mock|azure`로 구현체를 전환하며,
실제 엔드포인트 정보가 확정되면 `app/ml/azure.py`의 변환 함수 2개(`_to_aml_payload`/`_from_aml_response`)와 `.env`만 채우면 됩니다.

## 로컬 실행

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt      # 런타임 + 테스트
cp .env.example .env                      # 값 채우기 (API_KEY 등)
uvicorn app.main:app --reload
```

- Swagger UI: http://127.0.0.1:8000/docs
- 헬스체크: `GET /health` (인증·RateLimit 제외)
- 예측: `POST /api/v1/predict` (헤더 `X-API-Key: <API_KEY>`)

```bash
curl -X POST http://127.0.0.1:8000/api/v1/predict \
  -H "Content-Type: application/json" -H "X-API-Key: local-dev-key" \
  -d '{"inputs":[{"feature_a":0.5,"feature_b":12}]}'
```

전체 엔드포인트·에러 코드는 [SPEC.md](docs/SPEC.md) 참조.

## 주요 환경변수

| 키 | 기본값 | 설명 |
|---|---|---|
| `API_KEY` | `dev-local-key` | `X-API-Key` 기대값 |
| `ML_CLIENT` | `mock` | `mock` \| `azure` |
| `AZURE_ML_SCORING_URI` / `AZURE_ML_KEY` | (없음) | 실제 연동 시 |
| `CORS_ORIGINS` | `""` | 콤마 구분 허용 출처 |
| `RATE_LIMIT` | `60/minute` | IP 기준 근사 제한 |

전체 목록은 [.env.example](.env.example) / [TRD.md §7](docs/TRD.md) 참조.

## 테스트

```bash
pytest          # 23건 (health / auth / predict / validation / azure client / observability)
```

## 배포 (App Service, Code) — ✅ 배포 완료 (재배포는 승인)

배포는 멱등 스크립트 [`deploy.sh`](deploy.sh)로 수행합니다(App Settings 주입 → startup/헬스체크 설정 → zip OneDeploy → 스모크; transient 502 내성). 시작 명령은 [`startup.sh`](startup.sh):

```bash
gunicorn -w 2 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:${PORT:-8000} --timeout 600 app.main:app
```

시크릿은 커밋하지 않고 App Service **Application Settings**로 주입합니다
(`API_KEY`, `ML_CLIENT`, `AZURE_ML_SCORING_URI`, `AZURE_ML_AUTH_PRI_KEY`, `AZURE_ML_AUTH_SEC_KEY`, `CORS_ORIGINS`, `APPLICATIONINSIGHTS_CONNECTION_STRING`).
배포 대상·절차 상세는 [TRD.md §9](docs/TRD.md).

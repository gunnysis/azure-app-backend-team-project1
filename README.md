# azure-app-backend-team-project1

Azure ML 엔드포인트 연동용 FastAPI 백엔드 (BFF + ML 프록시).

- **런타임**: Python 3.14 / FastAPI
- **배포**: Azure App Service (Linux, **Code 배포** — Docker 아님)
- **설계 문서**: [`docs/design_backend.md`](docs/design_backend.md)

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

ML 호출은 `MLClient` 인터페이스 뒤로 격리됨. `ML_CLIENT=mock|azure`로 구현체 전환.
실제 엔드포인트 정보가 확정되면 `app/ml/azure.py`의 변환 함수 2개와 `.env`만 채우면 됨.

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
  -d '{"inputs":[1,2,3]}'
```

## 테스트

```bash
pytest
```

## 배포 (App Service, Code)

startup 명령은 [`startup.sh`](startup.sh):

```bash
gunicorn -w 2 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 --timeout 600 app.main:app
```

시크릿은 커밋하지 않고 App Service **Application Settings**로 주입
(`API_KEY`, `AZURE_ML_SCORING_URI`, `AZURE_ML_KEY`, `CORS_ORIGINS`, `ML_CLIENT`).

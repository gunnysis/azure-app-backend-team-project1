#!/bin/bash
# Azure App Service (Linux, Code 배포) 시작 명령.
# 공식 권장: gunicorn + UvicornWorker. App Service 가 주입하는 $PORT 에 바인딩(없으면 8000).
gunicorn -w 2 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:${PORT:-8000} --timeout 600 app.main:app

#!/bin/bash
# Azure App Service (Linux, Code 배포) 시작 명령.
# 공식 권장: gunicorn + UvicornWorker. 포트 8000 = Python Blessed Image 기본 노출 포트.
gunicorn -w 2 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 --timeout 600 app.main:app

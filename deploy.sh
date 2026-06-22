#!/usr/bin/env bash
# Azure App Service 배포 (Code/Oryx, OneDeploy zip) — 멱등 재실행 가능.
#
# ⚠️ Azure 리소스 변경/배포 → CLAUDE.md상 승인 후 실행.
# 시크릿은 이 스크립트에 없음: .env 에서 로드해 App Settings 로 주입(.env 는 커밋 금지).
# 사전: `az login` 완료, 리포 루트에 .env 존재.
#
# 사용: ./deploy.sh
set -euo pipefail

RG="${RG:-project-1st-team-3}"
APP="${APP:-app-mlbackend-prod-kc-01}"
cd "$(cd "$(dirname "$0")" && pwd)"

[ -f .env ] || { echo "ERROR: .env 가 없습니다." >&2; exit 1; }
# 주의: .env 의 값에 세미콜론(;)이 있으면 반드시 따옴표로 감싸야 한다.
# (예: APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=...;IngestionEndpoint=...")
# 따옴표가 없으면 아래 `source` 가 첫 ';' 에서 값을 잘라 truncated 시크릿이 주입된다.
set -a; . ./.env; set +a
: "${API_KEY:?API_KEY 필요}" "${AZURE_ML_SCORING_URI:?}" "${AZURE_ML_AUTH_PRI_KEY:?}"

# 재발방지: 연결문자열이 IngestionEndpoint 없이 truncated 되면(따옴표 누락 등) 텔레메트리가
# 글로벌 엔드포인트로 가 cross-origin redirect 로 누락된다 → 완전치 않으면 차라리 주입하지 않는다.
if [ -n "${APPLICATIONINSIGHTS_CONNECTION_STRING:-}" ] && \
   ! printf '%s' "$APPLICATIONINSIGHTS_CONNECTION_STRING" | grep -q "IngestionEndpoint"; then
  echo "WARN: APPLICATIONINSIGHTS_CONNECTION_STRING 에 IngestionEndpoint 없음(.env 따옴표 확인) — 주입 생략" >&2
  APPLICATIONINSIGHTS_CONNECTION_STRING=""
fi

echo "==> [1/4] Application Settings 주입 (값 미출력)"
az webapp config appsettings set -g "$RG" -n "$APP" --only-show-errors --output none --settings \
  API_KEY="$API_KEY" \
  ML_CLIENT=azure \
  AZURE_ML_SCORING_URI="$AZURE_ML_SCORING_URI" \
  AZURE_ML_AUTH_PRI_KEY="$AZURE_ML_AUTH_PRI_KEY" \
  AZURE_ML_AUTH_SEC_KEY="${AZURE_ML_AUTH_SEC_KEY:-}" \
  CORS_ORIGINS="${CORS_ORIGINS:-}" \
  RATE_LIMIT_ENABLED="${RATE_LIMIT_ENABLED:-true}" \
  RATE_LIMIT="${RATE_LIMIT:-60/minute}" \
  APPLICATIONINSIGHTS_CONNECTION_STRING="${APPLICATIONINSIGHTS_CONNECTION_STRING:-}" \
  SCM_DO_BUILD_DURING_DEPLOYMENT=true

echo "==> [2/4] 시작 명령(startup.sh) + 헬스체크 경로(/health)"
az webapp config set -g "$RG" -n "$APP" --startup-file "startup.sh" --only-show-errors --output none
az webapp update -g "$RG" -n "$APP" --set siteConfig.healthCheckPath="/health" --only-show-errors --output none

HOST="$(az webapp show -g "$RG" -n "$APP" --query defaultHostName -o tsv)"

# 재발방지: 위 config 변경들이 앱/SCM 재시작을 유발 → 곧바로 배포하면 SCM 이 재시작 중이라
# OneDeploy 가 transient 502 로 실패한다. 배포 전 readiness 게이트로 안정화를 기다린다.
echo "==> readiness 대기 (config 변경 후 재시작 안정화)"
curl -s -o /dev/null --retry 12 --retry-delay 10 --retry-all-errors --retry-connrefused --max-time 30 "https://$HOST/health" || true

echo "==> [3/4] 코드 패키징(앱만; .env/.venv/tests/docs 제외) + OneDeploy"
rm -f deploy.zip
zip -rq deploy.zip app startup.sh requirements.txt -x '*__pycache__*' '*.pyc'
# 재발방지: deploy CLI 의 502 는 SCM 재시작 중 false-negative 일 수 있다. 최대 3회 재시도하되,
# 최종 성공 판정은 CLI 종료코드가 아니라 아래 [4/4] 의 /health 200 으로 한다.
for attempt in 1 2 3; do
  if az webapp deploy -g "$RG" -n "$APP" --src-path deploy.zip --type zip --only-show-errors; then break; fi
  echo "  deploy 시도 ${attempt} 실패(흔히 SCM 재시작 중 transient 502) — readiness 후 재시도..."
  curl -s -o /dev/null --retry 10 --retry-delay 12 --retry-all-errors --retry-connrefused --max-time 30 "https://$HOST/health" || true
done

echo "==> [4/4] 스모크 (성공 판정 = /health 200)"
hc="$(curl -s -o /dev/null -w '%{http_code}' --retry 18 --retry-delay 12 --retry-all-errors --retry-connrefused --max-time 30 "https://$HOST/health" || true)"
echo "GET /health -> ${hc}"
[ "$hc" = "200" ] || { echo "ERROR: /health 가 200 이 아닙니다 — 로그: az webapp log tail -g $RG -n $APP" >&2; exit 1; }
echo "POST /api/v1/predict ->"
curl -sS --max-time 60 -X POST "https://$HOST/api/v1/predict" \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"inputs":[{"prev_year_usage":76,"avg_temp":-0.46,"avg_humidity":66.55,"total_rainfall":21.1,"current_usage":53,"thi":36.1076813,"month_sin":0.5,"month_cos":0.8660254037844387}]}'
echo
echo "DONE."

"""test4 엔드포인트 수동 스모크 테스트 (Azure 'Consume' 스니펫 기반, 계약 반영).

※ 실제 백엔드 호출 로직은 app/ml/azure.py 가 담당한다. 이 파일은 엔드포인트 단독
   점검용 1회성 스크립트이며 패키지로 import 되지 않는다(모든 동작은 __main__ 가드 안).
   (파일명 'comsume' 는 'consume' 오타 — 참조 호환 위해 유지)

키/URI 는 .env 에서 읽는다(pydantic-settings):
  AZURE_ML_AUTH_PRI_KEY (primary) 우선, 없으면 AZURE_ML_AUTH_SEC_KEY.
  AZURE_ML_SCORING_URI (없으면 아래 기본 test4 URL).
실행:  python -m app.ml.comsume   (수동 키 export 불필요 — .env 자동 로드)
검증된 계약(swagger): 요청 {"Inputs":{"input1":[...]},"GlobalParameters":{}}
                      응답 {"Results":{"WebServiceOutput0":[{..., "Scored Labels": ...}]}}
"""

import json
import urllib.error
import urllib.request

from app.config import get_settings

DEFAULT_URL = "http://7924e88e-ebe7-44eb-8e63-1b49ea44aa93.koreacentral.azurecontainer.io/score"

# swagger example 의 입력 1행 (8개 피처). 실제 점검 시 값만 교체.
SAMPLE = {
    "Inputs": {
        "input1": [
            {
                "prev_year_usage": 76,
                "avg_temp": -0.46,
                "avg_humidity": 66.55,
                "total_rainfall": 21.1,
                "current_usage": 53,
                "thi": 36.1076813,
                "month_sin": 0.5,
                "month_cos": 0.8660254037844387,
            }
        ]
    },
    "GlobalParameters": {},
}


def main() -> None:
    settings = get_settings()
    api_key = settings.azure_ml_key  # primary 우선, 없으면 secondary (config 속성)
    if not api_key:
        raise SystemExit(
            ".env 에 AZURE_ML_AUTH_PRI_KEY(또는 SEC_KEY)가 필요합니다 (커밋·로그 금지)."
        )
    url = settings.azure_ml_scoring_uri or DEFAULT_URL

    body = json.dumps(SAMPLE).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    req = urllib.request.Request(url, body, headers)
    try:
        with urllib.request.urlopen(req) as resp:
            print(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        # 헤더에 request id·timestamp 가 있어 실패 진단에 유용.
        print(f"HTTP {error.code}")
        print(error.info())
        print(error.read().decode("utf-8", "ignore"))


if __name__ == "__main__":
    main()

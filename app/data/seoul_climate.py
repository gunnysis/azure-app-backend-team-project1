"""서울(마포) 월별 기후평년값 — 어댑터 피처빌더의 기상 입력원.

출처: 기상청 기후평년값(1991~2020), 서울 종관관측소(지점번호 108).
  https://data.kma.go.kr/normals/table.do

마포구는 별도 종관관측소가 없어, 인접한 도심 표준 관측소인 **서울(108)** 평년값을
마포 대리값(proxy)으로 사용한다. 1개 지역(마포) MVP 범위에서 충분하며, 지역이
늘어나면 지점별 테이블로 확장한다.

각 월 → (avg_temperature[°C], avg_humidity[%], total_rainfall[mm]).
모델 입력 피처명(avg_temperature/avg_humidity/total_rainfall)과 1:1 대응한다.
"""

# month(1~12) → (평균기온 °C, 평균 상대습도 %, 월 강수량 mm)
SEOUL_MONTHLY_NORMALS: dict[int, tuple[float, float, float]] = {
    1: (-2.0, 56.2, 16.8),
    2: (0.7, 54.6, 28.2),
    3: (6.1, 54.6, 36.9),
    4: (12.6, 54.8, 72.9),
    5: (18.2, 59.7, 103.6),
    6: (22.7, 65.7, 129.5),
    7: (25.3, 76.2, 414.4),
    8: (26.1, 73.5, 348.2),
    9: (21.7, 66.4, 141.5),
    10: (15.0, 61.8, 52.2),
    11: (7.5, 60.4, 51.1),
    12: (0.2, 57.8, 22.6),
}


def monthly_weather(month: int) -> tuple[float, float, float]:
    """주어진 월(1~12)의 (평균기온, 평균습도, 강수량)을 반환."""
    if month not in SEOUL_MONTHLY_NORMALS:
        raise ValueError(f"month must be 1..12, got {month!r}")
    return SEOUL_MONTHLY_NORMALS[month]

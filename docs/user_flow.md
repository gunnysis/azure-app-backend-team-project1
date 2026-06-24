[ 프론트엔드 (UI) ]
       │  1. 유저 입력 전송 (평수, 에어컨 시간, 구청코드, 선택 월)
       ▼
[ 우리 백엔드 서버 (API) ]
       │  2. 피처 복원 (평수/시간 ➔ 가상 전년사용량 계산)
       │  3. 날씨 데이터 매핑 (기온, 습도, 강수량, 불쾌지수 매핑)
       │  4. Azure ML 형식에 맞는 JSON 페이로드 구성
       │  
       │  5. REST API 호출 (with Bearer Token 인증)
       ▼
[ Azure ML 엔드포인트 ] ➔ 6. 모델 추론 ➔ 7. 예측 사용량(Scored Labels) 반환
       │
       ▼
[ 우리 백엔드 서버 (API) ]
       │  8. 반환된 사용량 수신
       │  9. 최종 예측 사용량 + 최종 계산 금액 패키징
       ▼
[ 프론트엔드 (UI) ]
          10. 화면에 멋진 그래프와 예상 요금 고지서 렌더링

---

> **⚠️ 2단계 피처 라우팅 주의 (발견 C, 2026-06-24 해소)**
> 모델이 **반응하는 입력 피처는 `prev_year_usage`** 다(단일 지배 예측자, 상관 0.85). 반면
> `current_usage`는 모델의 **학습 라벨(예측 타깃)** 이라 요청에 넣어도 **무시**된다. 따라서 2단계의
> "가상 전년사용량"은 에어컨 습관 신호를 **`prev_year_usage` 슬롯**으로 라우팅한 것이고, 7단계
> 반환값은 `current_usage`가 아니라 **`Scored Labels`**(모델 출력)다.
> 근거·캘리브레이션: [`plans/electric_calculator_act_plan.md`](plans/electric_calculator_act_plan.md),
> [`user_flow_review.md`](user_flow_review.md) §6.
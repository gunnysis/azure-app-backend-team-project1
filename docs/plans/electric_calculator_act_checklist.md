# 과제 체크리스트 — 발견 C(ML이 에어컨 입력 무시) 해소

설계·근거: [`electric_calculator_act_plan.md`](electric_calculator_act_plan.md)

- [x] **근본 원인 규명**: 배포 모델이 `current_usage`를 무시하는 건 그게 **학습 라벨**이라서(AML 데이터 포렌식 확정). 모델 반응 피처는 `prev_year_usage`(상관 0.85).
- [x] **방식 확정**: 에어컨 추정치를 `prev_year_usage` 피처로 라우팅(Approach A). *초기 안의 `136 + (h×0.65×30×0.60)` 직산식 → 기존 타입인지 `estimate_usage` 재사용 + 듀티 0.60·clamp 400으로 정제(상수 3중분기 방지).*
- [x] **구현**: 백엔드 `feature_builder`(`15d1e84`) + 프론트 미러(`2b4b441`).
- [x] **검증**: pytest 48 passed · 정합 그리드 220케이스 0 불일치 · 백엔드 prev 곡선 = 라이브 /predict 검증값.
- [ ] **배포**(승인 필수): 백엔드 `deploy.sh` + 프론트 push(=SWA). 배포 후 라이브 스윕 0→24 단조·predicted>baseline 확인.

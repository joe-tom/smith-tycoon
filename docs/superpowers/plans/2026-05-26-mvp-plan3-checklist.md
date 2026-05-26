# Plan 3 수동 검증 체크리스트

## 사전
- [ ] backend pytest 모두 PASS (70+)
- [ ] frontend `tsc --noEmit` 통과
- [ ] uvicorn + vite 재기동

## 호감도 + 가격 보정
- [ ] Day 1 hero에게 후한 가격 (시세 -10% 미만) 판매 → 호감도 +10
- [ ] Day 1 hero에게 적정가 판매 → 호감도 +5
- [ ] Day 1 hero에게 바가지 (시세 +20% 초과)로 판매 → 호감도 -10
- [ ] 호감도 ≥ +20 hero 재방문 시 NegotiationChat 호감도 초록색 + 별명 표시
- [ ] 호감도 ≥ +50 hero → 시세 110%까지 자동 수락
- [ ] 호감도 ≤ -50 hero → 즉시 reject ("당신과는 거래하지 않겠소") + phase 진행, 평판 변화 없음
- [ ] 무기 파괴 전투 후 hero affinity -5

## 강화 흐름
- [ ] Day 1 hero1에 판매 → 전투 무기 보존 → held_weapon_id 세팅
- [ ] Day 4 같은 hero 재방문 → DayRouter가 EnhanceNegotiation 렌더 (재료 선택 UI)
- [ ] 일반 재료 1개 강화 → 예리도 +1~3, 희귀도 +0~2
- [ ] 특수 재료 1개 강화 → 예리도 +3~7, 희귀도 +2~5
- [ ] 전설 재료 1개 강화 → 예리도 +7~15, 희귀도 +5~12
- [ ] 강화 후 weapons.enhancement_level +1, materials_used에 action='enhance' 항목 추가
- [ ] 강화 비용 협상이 매도와 동일하게 accept/counter/reject 분기
- [ ] 강화 합의 시 평판 +1
- [ ] 강화 결렬 시 평판 -1
- [ ] 강화 phase skip → 평판 변화 없음

## 별명 부여
- [ ] 같은 hero가 연속 2회 (생존+마왕 처치) + 호감도 ≥20 달성 → 전투 직후 별명 부여
- [ ] 별명 부여 후 헤더에 `{name} "{nickname}"` 형태로 표시
- [ ] 한 번 부여되면 nickname 갱신 안 됨 (재발동 X)
- [ ] day_events에 kind='nickname' 기록 (DaySummary 로그에 표시)

## 회상 대사
- [ ] 호감도 ≥20 hero와 협상 시 LLM 대사에 회상 자연스럽게 포함 ("지난번 그 검 잘 쓰고 있소" 등)
- [ ] history_recent에 최근 거래 5건이 LLM 프롬프트에 들어가는지 확인 (필요 시 로그)

## 일일 요약 로그
- [ ] DaySummary 이벤트 로그에 'enhance', 'nickname' 종류도 한글 포맷으로 표시되는지 확인
  - 강화 이벤트 포맷이 없으면 [`enhance`: {...}] 형태로 fallback 됨 — 필요 시 DaySummary.tsx의 formatEvent에 case 추가

## 미포함 (Plan 4+)
- 시그니처 기법
- 전설 무기 등재
- 보스 전투, 5행 속성 상성
- 승리·패배 엔딩

## 발견된 LLM 품질 이슈

| 시나리오 | 관찰 | 메모 |
|---|---|---|
|   |   |   |

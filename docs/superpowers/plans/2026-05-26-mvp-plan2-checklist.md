# Plan 2 수동 검증 체크리스트

## 사전
- [x] Supabase에 `backend/migrations/002_daily_loop.sql` 적용 (MCP `apply_migration`로 완료)
- [x] 신규 테이블 2개 (`merchants_today`, `day_events`) 존재
- [x] `heroes.held_weapon_id` 컬럼 존재
- [x] 9개 테이블 RLS 활성·`materials_anon_read` 정책 존재
- [ ] uvicorn + vite 재기동

## 5일 골든 패스 (실제 LLM)
- [ ] 새 게임 시작 → SidePanel에 Day 1 / 5 표시
- [ ] forge_open 제작 또는 skip 동작
- [ ] hero1 협상 → 전투
- [ ] 상인 협상 (counter → accept) → 인벤토리에 재료·무기 추가, 금화 차감
- [ ] hero2 협상 → 전투
- [ ] forge_open_2 제작 또는 skip
- [ ] hero3 협상 → 전투
- [ ] day_summary — 이벤트 리스트·요약 통계 표시
- [ ] "다음 날" → Day 2 forge_open
- [ ] Day 2에서 Day 1 생존 용사가 재방문 (return_day=4면 Day 4에서 등장)
- [ ] Day 5 day_summary 후 "다음 날" → GameOver 화면

## 전투 강화 검증
- [ ] Day 1에서 맨손 전투 시 부상·사망 빈도 증가 (체감)
- [ ] Day 5에서 demon 난이도 20+ 등장, 강한 무기 없이 이기기 어려움

## 상인 협상
- [ ] 묶음 시세 표시 합리적
- [ ] counter / accept / reject 분기 모두 동작
- [ ] 즉시 거절 시 평판 변화 없음, 협상 후 거절 시 -1
- [ ] skip 버튼 동작 (평판 변화 없음)

## forge skip
- [ ] forge_open 단계에서 "건너뛰기" 동작
- [ ] forge_open_2 단계에서 "건너뛰기" 동작

## RLS 검증
- [ ] anon 키로 Supabase 대시보드에서 `players` SELECT → 0 rows
- [ ] anon 키로 `materials` SELECT → 20 rows
- [ ] 백엔드는 service_role 사용해 정상 동작

## LLM 비용
- [ ] `GET /llm/usage` 호출해 5일 풀 플레이 누적 USD 확인
- [ ] 한 일차당 LLM 호출 ~10번 예상 (forge 2×2=4, 협상 3~9, 전투 3)

## 미포함 (Plan 3 예정)
- 단골 호감도 효과 (회상 대사, 가격 보정 등)
- 무기 강화 협상
- 시그니처/전설 무기

## 미포함 (Plan 4+ 예정)
- 중간보스·최종보스
- 5행 속성 상성

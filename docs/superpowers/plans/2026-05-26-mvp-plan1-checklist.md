# Plan 1 수동 검증 체크리스트

작성일: 2026-05-26
대상: `feat/mvp-plan1-slice` 브랜치

실제 LLM API 키로 한 번, 픽스처 모드로 한 번 검증.

## 사전 준비

- [ ] `backend/.env` 작성 (`backend/.env.example` 복사 후 채움)
  - `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`
  - `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`
- [ ] Supabase 프로젝트 SQL Editor에 `backend/migrations/001_initial.sql` 붙여넣고 실행
- [ ] 7개 테이블 생성 확인 (players, materials, inventory, weapons, heroes, negotiations, battles)
- [ ] 백엔드 의존성 설치: `cd backend && python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"`
- [ ] 프론트엔드 의존성 설치: `cd frontend && npm install`
- [ ] 백엔드 기동: `cd backend && . .venv/bin/activate && uvicorn app.main:app --port 8000 --reload`
- [ ] 프론트엔드 기동: `cd frontend && npm run dev`

## 골든 패스 — 실제 LLM 모드

- [ ] `http://localhost:5173` 접속 → "새 게임 시작" 클릭
- [ ] SidePanel 확인: 금화 5000, 평판 0, Phase `forge_open`, 인벤토리 7종, 진열장 비어 있음
- [ ] ForgePanel에서 재료 2~3개 선택 + 양손검 선택 → "제작하기"
- [ ] 진열장에 새 무기 1개 추가, Phase가 `hero_negotiate`로 전환
- [ ] NegotiationChat 표시: 용사 이름·직업·기분·성격·금화, 무기 정보
- [ ] 가격 1000, "튼튼한 검이오" 입력 → 제안하기
- [ ] 채팅에 용사 응답 (한국어 대사) 노출
- [ ] decision = accept → "확정" 버튼 → 금화 ↑·평판 +1, Phase `hero_battle`
- [ ] decision = counter → 카운터 가격 자동 반영, 재제안 가능
- [ ] decision = reject → "다음으로" (slice 한계: phase 그대로)
- [ ] BattleResult에 LLM 뉴스 단락 + 결과 3종 표시
- [ ] "다음으로" → "슬라이스 종료" 화면

## 골든 패스 — 픽스처 모드

`.env`에 `LLM_FIXTURE_DIR=tests/fixtures/llm` 추가 후 재시작.

- [ ] 위 시나리오를 픽스처 응답으로 재현 (무기명 "원목 양손검", 협상 accept, 전투 "라엘이 …")
- [ ] LLM 호출 없음을 확인 (네트워크 탭에 외부 호출 없음)

## 에러 경로

- [ ] 재료 0개 상태에서 제작 시도 → 토스트 (재료 부족)
- [ ] phase 우회: forge_open이 아닐 때 `curl -X POST localhost:8000/forge` → 400 + `wrong_phase`
- [ ] LLM 모델명을 잘못 설정 → 에러 토스트, 게임 계속 가능 (3회 재시도 후 폴백 없이 실패 표시. MVP 한계)

## 정성 점검 (LLM 품질)

- [ ] 협상 대사가 용사 성격(`personality_tags`)에 어울리는가
- [ ] 전투 스크립트가 무기명과 적 이름을 모두 언급하는가
- [ ] 가격 제시가 무기 시세에 비례하는 범위인가 (서버 clamp가 합리적인가)
- [ ] 한국어가 자연스러운가

## 발견된 이슈 기록

수동 플레이 중 LLM 응답 품질 이슈는 아래에 적고, 종합은 `docs/llm-eval/2026-05-26.md`로.

| 항목 | 시나리오 | 관찰 | 조치 후보 |
|---|---|---|---|
|   |   |   |   |

## 완료 조건

- [ ] 사전 준비 전부 완료
- [ ] 실제 LLM 골든 패스 통과
- [ ] 픽스처 모드 골든 패스 통과
- [ ] 에러 경로 3개 확인
- [ ] 정성 점검 4항 통과

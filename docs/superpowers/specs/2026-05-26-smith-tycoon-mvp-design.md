# 대장장이 Tycoon MVP — 설계 문서

작성일: 2026-05-26
원본 게임 설계: [../../../architecture.md](../../../architecture.md)

---

## 0. 목적 & 비검증 가설

MVP의 단 하나의 목적은 **"LLM 협상이 게임 흐름 안에서 재미있는가"** 를 검증하는 것이다.

검증 가설:
- 플레이어가 가격을 제시하고 NPC가 LLM으로 응답하는 협상 루프가 반복해도 지루하지 않다
- 용사 측 협상(판매)과 상인 측 협상(구매)이 둘 다 의미 있는 결정이 된다
- 단골 용사의 기억·호감도가 협상의 톤을 바꿔서 "내 대장간 이야기" 감각이 시작된다

비목표:
- 100일 풀 게임의 균형
- 보스·시그니처·전설 무기 등 메타 진행
- 미려한 UI·애니메이션

---

## 1. 스코프

### 1.1 포함

- 무기 제작 (재료 → Weapon, LLM이 이름·스킬 생성)
- 용사 협상 (무기 판매)
- 상인 협상 (재료·무기 구매)
- 전투 (LLM 뉴스 스크립트 + 결과 코드)
- 강화 협상 (재방문 용사가 무기 보존 시 분기)
- 단골 호감도 (기억·회상으로 협상 톤 변화)
- 3~5일 루프, 종료 시 요약

### 1.2 제외 (architecture.md의 다음 시스템은 MVP에 없음)

- 시그니처 기법 (§13.1)
- 전설 무기 등재 (§13.2)
- 마왕군 난이도 곡선 (§8.2)
- 중간보스·최종보스 (§8.3)
- 5행 속성 상성 계산 (§3.4) — LLM 서술로 대체
- 승리·패배 엔딩 (§14)

### 1.3 핵심 경험

- 핵심 루프: `제작 → 용사1 협상→전투 → 상인 협상 → 용사2 협상→전투 → 제작 → 용사3 협상→전투 → 요약`
- 시간 규모: 3~5일 (사용자 설정. 기본 3일)
- 종료 조건: 마지막 날 phase 완료 시 최종 요약 화면

---

## 2. 기술 스택

| 레이어 | 선택 | 이유 |
|---|---|---|
| 프론트 | React + Vite (TypeScript) | SPA로 충분, SSR 불필요 |
| 백엔드 | Python + FastAPI | LLM 프롬프트 조작·실험 편의 |
| DB | Supabase (Postgres) — `repo` 모듈을 통해서만 접근 | 호스팅·관리 부담 없음 |
| LLM | OpenAI 호환 `/chat/completions` API | 제공자 교체 자유 |
| 인증 | 없음 (player_id=1 하드코딩) | 단일 사용자 MVP |

---

## 3. 시스템 아키텍처

```
┌────────────────────────┐
│   Browser (SPA)        │   React + Vite
│   - DayRouter          │
│   - NegotiationChat    │
│   - ForgePanel 등      │
└──────────┬─────────────┘
           │ REST (JSON)
┌──────────▼─────────────┐
│   Backend (FastAPI)    │   Server-authoritative
│   - state_machine      │
│   - negotiation/forge/ │
│     combat/hero_registry│
│   - llm gateway        │
│   - repo               │   ← Supabase 클라이언트는 여기만
└──────────┬─────────────┘
           │
┌──────────▼─────────────┐
│   Supabase (Postgres)  │
└────────────────────────┘

┌────────────────────────┐
│   OpenAI 호환 LLM API   │
└────────────────────────┘
```

### 3.1 핵심 원칙

- **Server-authoritative**: phase 전환·LLM 호출·평판·금화 계산은 백엔드가 책임. 프론트는 표시 + 사용자 입력 전달.
- **REST 단일 호출 + 폴링 없음**: 협상 한 라운드마다 동기 POST. 스트리밍·웹소켓 없음.
- **LLM 응답을 신뢰하지 않음**: LLM은 `decision`과 `counter_price`를 *제안*만 함. 가격 clamp·평판 변화 등 실제 게임 상태 적용은 서버 로직이 결정.

---

## 4. 모듈 구성

### 4.1 백엔드

| 모듈 | 책임 | LLM 호출 |
|---|---|---|
| `state_machine` | 일일 페이즈 전환. 현재 phase 검증·다음 phase 결정 | — |
| `forge` | 재료 리스트 → Weapon. 스탯 분포 (정규분포, 시드 고정 가능) | 무기 이름, 스킬 |
| `negotiation` | 대화 라운드 상태 보관. LLM 응답 파싱·가격 clamp·평판 적용 | 협상 응답 |
| `combat` | 용사 + 무기 + 마왕군 1마리 → 결과 코드 + 뉴스 텍스트 | 전투 스크립트 |
| `hero_registry` | 용사 생성·기억·호감도. 재방문 시 프롬프트 컨텍스트 빌드 | 첫 등장 시 이름·성격 |
| `repo` | Supabase 호출 집중. 다른 모듈은 repo만 통해 DB 접근 | — |
| `llm` | OpenAI 호환 클라이언트 래퍼. 재시도·JSON 파싱·픽스처 모의 모드 | (게이트웨이) |
| `api` | FastAPI 라우터. URL → 모듈 호출 → 응답 직렬화 | — |

### 4.2 프론트엔드

| 컴포넌트 | 책임 |
|---|---|
| `<DayRouter>` | 서버 phase 읽어 그에 맞는 컴포넌트 스왑 |
| `<ForgePanel>` | 재료 선택 → 제작 → 결과 카드 |
| `<NegotiationChat>` | 채팅 UI + 가격 입력. 라운드마다 백엔드 POST |
| `<MerchantPanel>` | 상인 인벤토리 + 다중 선택 → 협상 진입 |
| `<BattleResult>` | LLM 뉴스 텍스트 + 결과 코드 (모달) |
| `<DaySummary>` | 평판·금화·전투 결과 요약 |
| `<SidePanel>` | 인벤토리·진열장·금화·평판 (항상 표시) |

### 4.3 모듈 간 통신 원칙

- 모듈 간 직접 함수 호출 + 평이한 데이터 객체. 이벤트 버스 없음.
- `repo`만 Supabase 의존성을 가짐 — 다른 모듈은 DB 갈아끼우기 쉬움, 테스트 용이.

---

## 5. 데이터 모델

```sql
-- 단일 플레이어 MVP. player_id = 1 고정
players (
  id PK, gold int, reputation int, craft_power int,
  current_day int, current_phase text
)

materials (id PK, name, category, attribute, base_price)  -- 카탈로그, 시드
inventory (player_id FK, material_id FK, qty)

weapons (
  id PK, player_id FK, owner: 'player'|'hero'|'sold',
  name, type, rarity int, sharpness int, attribute,
  skill text, str_req int, mag_req int, enhancement_level int,
  materials_used jsonb, created_day int
)

heroes (
  id PK, name, job, str int, mag int, gold int, mood text,
  personality_tags text[], affinity int,
  nickname text, return_day int,
  status: 'alive'|'fled'|'dead',
  history jsonb  -- 최근 5건의 (weapon_name, agreed_price, battle_outcome)
)

merchants_today (id PK, day int, inventory jsonb)

negotiations (
  id PK, player_id FK, day int, phase text,
  kind: 'sell'|'buy'|'enhance',
  counterparty_id,  -- hero_id 또는 merchant_id
  weapon_id?, materials? jsonb,
  rounds jsonb,  -- [{role, message, price}, ...]
  outcome: 'accepted'|'rejected'|'open',
  agreed_price?
)

battles (
  id PK, player_id FK, day int,
  hero_id FK, weapon_id?,
  demon jsonb,  -- {type, attribute, difficulty}
  script_text text,
  outcomes jsonb  -- {hero: 'survived'|..., weapon: 'preserved'|..., demon: ...}
)

day_events (id PK, player_id FK, day int, kind text, payload jsonb)
```

`heroes.history`, `negotiations.rounds`, `merchants_today.inventory`는 jsonb 한 컬럼으로 비정규화. MVP에서는 조회·집계가 필요 없어 정규화 비용이 안 맞음.

---

## 6. 데이터 플로우 — 단일 phase 예시 (용사1 협상)

```
[Client]                            [API]                   [Modules]                [LLM]
GET /state         ─────────►       state_machine.current() → repo.load_player()
                                    ◄── { phase: "hero1_negotiate", hero, weapons_for_sale }

POST /negotiate    ─────────►       negotiation.step(
  { weapon_id,                         msg, weapon, hero,
    price_offered,                     prior_rounds )
    player_message }                                         ── prompt ──►   LLM
                                                              ◄── JSON { decision, message, counter_price }
                                    ◄── { decision, message, round_id }

(decision = accept일 때)
POST /negotiate/finalize ──►        negotiation.finalize() → repo.transfer_weapon()
                                                             repo.update_gold/reputation()
                                                             hero_registry.record_purchase()
                                    ◄── { ok, next_phase: "hero1_battle" }

POST /battle       ─────────►       combat.run(hero, weapon) ── prompt ──►   LLM
                                                              ◄── { script, outcomes }
                                    ◄── { script, outcomes, next_phase }
```

### 6.1 LLM 출력 스키마 (협상 예시)

```json
{
  "decision": "accept" | "reject" | "counter",
  "counter_price": 1234,  // counter일 때만
  "message": "..."         // 화면용 NPC 대사
}
```

- `llm` 모듈이 JSON 파싱 실패 시 1회 재시도 (스키마 위반 명시한 시스템 메시지 추가)
- 2회 실패 시 안전한 기본값으로 폴백
- 모든 프롬프트는 정적 파일(`prompts/*.j2`)로 보관 — 코드 빌드 없이 튜닝 가능

### 6.2 phase 전환 강제

클라이언트가 잘못된 phase에서 호출하면 400 + 현재 phase 응답. 클라이언트 버그가 게임 상태를 망가뜨릴 수 없음.

---

## 7. 에러 처리 & 엣지 케이스

### 7.1 LLM

| 상황 | 처리 |
|---|---|
| HTTP 5xx / 타임아웃 | `llm`에서 지수 백오프 2회 재시도 (총 3회) |
| JSON 파싱 실패 | "스키마 위반" 시스템 메시지로 1회 재요청 |
| 2회 실패 | 안전한 폴백 — 협상: `reject + "지금은 거래가 어렵겠소"`, 전투: 무승부 + 일반 텍스트 |
| 가격이 음수·천문학적 | 서버에서 clamp (무기 base_price × [0.1, 5.0]) |

LLM 응답은 절대 신뢰하지 않음. 게임 상태 변화는 서버 로직이 결정.

### 7.2 클라이언트 ↔ 서버

| 상황 | 처리 |
|---|---|
| 잘못된 phase | 400 + `{error: "wrong_phase", current_phase: "..."}`. 프론트는 `/state` 재조회 |
| 재료·금화 부족 | 400 + 사유 코드. 토스트 표시 |
| 네트워크 끊김 | 마지막 응답 유지 + 재시도 버튼. 자동 재시도 없음 |
| 중복 요청 | 상태 변경 엔드포인트는 idempotency key(client UUID). 같은 키 재호출 시 캐시 응답 |

### 7.3 게임 상태

| 상황 | 처리 |
|---|---|
| 새 게임 | `POST /game/reset` — 게임 데이터 truncate + 시드 재삽입 |
| 새로고침 | 서버 상태가 진실. 화면만 다시 그림. 세션 개념 없음 |
| 동시성 | 단일 사용자 MVP라 무시. 프론트가 in-flight 동안 버튼 disable |

### 7.4 의도적 미처리

- 다중 사용자·동시성
- 인증·인가 (Supabase Auth 미사용)
- 세이브 슬롯 (게임 1개)
- 거래 취소·언두
- 오프라인 모드

### 7.5 LLM 다운 시 사용자 경험

게임은 폴백으로 계속 진행. UI에 "지금 NPC가 평소처럼 반응하지 않습니다 (LLM 응답 실패)" 토스트.

---

## 8. 테스트 전략

### 8.1 백엔드 단위 테스트 (pytest)

| 대상 | 검증 |
|---|---|
| `state_machine` | phase 전환이 정의된 순서대로만 일어남. 잘못된 phase에서 거부 |
| `forge` | 같은 재료 + 시드 → 결정적 스탯 (LLM 모킹) |
| `negotiation.apply_result` | LLM 응답 픽스처 → 금화·평판·인벤토리 변화가 규칙대로 |
| `combat.apply_outcome` | 결과 코드별 평판·무기 상태 변화 |
| `hero_registry` | 호감도 트리거(§12.2)별 증감. 별명·기억 직렬화 |
| `repo` | 통합 테스트로 분리. 단위 테스트는 페이크 repo |

### 8.2 LLM 게이트웨이

`llm` 모듈은 두 모드:
- 실제 모드: API 키 있을 때 진짜 호출
- 모의 모드: `LLM_FIXTURE_DIR` 환경변수 → 파일에서 응답 읽음

단위·통합 테스트는 모의 모드. 실제 LLM 호출은 수동 검증.

### 8.3 통합 테스트 (1~2개)

- "하루 골든 패스" 시나리오. 픽스처 LLM 응답으로 결정적.

### 8.4 프론트엔드

자동화된 컴포넌트 테스트 없음. 대신:
- TypeScript 타입체크
- 수동 골든 패스 체크리스트

이유: UI는 LLM 튜닝 중 자주 바뀜. 백엔드가 server-authoritative라 UI 버그가 게임 상태를 깨뜨리지 못함.

### 8.5 LLM 품질 평가 (수동)

`prompts/` 변경마다 골든 시나리오 5~10개 수동 플레이. 결과를 `docs/llm-eval/YYYY-MM-DD.md`에 기록.

### 8.6 미포함

- E2E 자동화 (Playwright)
- 부하·시각 회귀 테스트
- 100% 커버리지

---

## 9. 배포 & 운영

MVP는 로컬 실행만 가정.

- 백엔드: `uvicorn` 직접 실행 (`uvicorn app.main:app --reload`)
- 프론트: `vite dev`
- Supabase: 호스티드 프로젝트 사용. `.env`에 URL·anon key·service key 보관
- LLM API: `.env`에 base URL·API key
- 모든 시크릿은 `.env` 파일 (커밋 금지). `.env.example` 제공

배포 자동화·CI는 MVP 이후.

---

## 10. 디렉토리 구조 (제안)

```
smith-tycoon/
├── architecture.md                    (원본 설계)
├── docs/
│   └── superpowers/specs/             (이 문서)
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/                       (FastAPI 라우터)
│   │   ├── state_machine.py
│   │   ├── forge.py
│   │   ├── negotiation.py
│   │   ├── combat.py
│   │   ├── hero_registry.py
│   │   ├── repo.py
│   │   └── llm/                       (게이트웨이 + 프롬프트)
│   │       ├── client.py
│   │       └── prompts/*.j2
│   └── tests/
└── frontend/
    ├── src/
    │   ├── components/
    │   ├── pages/
    │   └── api.ts                     (백엔드 호출 래퍼)
    └── ...
```

---

## 11. 열린 결정 (구현 계획 작성 시 정해야 할 것)

- 모델 선택: 구체적인 LLM 모델 이름 (기본값 후보: 협상엔 강한 모델, 전투 스크립트엔 빠른 모델)
- Supabase 마이그레이션 도구: SQL 파일 직접 vs Supabase CLI
- 프론트 상태 관리: React Query / Zustand / 둘 다 — 결정 보류
- 재료 시드 데이터: architecture.md §4의 220종을 어떻게 정의할지 (JSON 파일 vs SQL seed)
- 일별 용사 풀: 매일 새 용사를 LLM이 생성할지, 미리 시드된 후보 풀에서 뽑을지

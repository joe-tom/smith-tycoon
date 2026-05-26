# MVP Plan 2 — 다일 루프 & 상인 설계 문서

작성일: 2026-05-26
선행: [Plan 1 spec](2026-05-26-smith-tycoon-mvp-design.md), [원본 설계](../../../architecture.md)

Plan 2는 Plan 1의 vertical slice를 **5일짜리 다일 운영 게임**으로 확장한다. 단골 호감도와 무기 강화는 Plan 3에 분리.

---

## 0. 목적 & 가설

핵심 가설:
- 5일에 걸쳐 용사 협상·상인 협상·전투가 반복돼도 LLM 협상이 지루해지지 않는다
- 일일 운영 시뮬레이션(자금·평판·재료 관리) 감각이 잡힌다
- 같은 용사가 재방문하는 경험이 의미 있다 (호감도 효과는 Plan 3에서 살림)

비목표:
- 단골 호감도 prompt 반영 (Plan 3)
- 무기 강화 시스템 (Plan 3)
- 보스·중간보스·5행 속성 (Plan 3+)

---

## 1. 스코프

### 1.1 포함

- **5일 다일 루프** + 일일 phase 시퀀스 (architecture.md §6)
- **상인 협상** (재료 묶음 + 무기 1개 — 예리도 30·희귀도 30)
- **재방문 용사 규칙** (architecture.md §9): 생존 3일 내 / 도망 7일 내 / 사망 X
- **일일 요약** 화면 (`day_summary` phase + `<DaySummary>` 컴포넌트)
- **전투 강화**: 프롬프트 보강 + day 비례 demon 난이도
- **Supabase RLS** 정책 (전수 활성 + materials만 anon SELECT)

### 1.2 제외

- 단골 호감도 누적 효과·LLM 프롬프트 회상 반영 (Plan 3)
- 무기 강화 협상 (Plan 3)
- 시그니처·전설 무기 (Plan 4+)
- 중간보스·최종보스 (Plan 4+)
- 5행 속성 상성 계산 (Plan 4+)

### 1.3 종료 조건

`day_summary` 화면에서 "다음 날" 버튼:
- day < 5 → 다음 날 시작 (day+1, phase=forge_open)
- day == 5 → `game_over` phase. 최종 통계 + "새 게임" 버튼

---

## 2. 일일 phase 시퀀스 & 상태 머신

```
하루의 phase (순서대로):
  forge_open           ← 1차 제작 (선택, skip 가능)
  hero1_negotiate
  hero1_battle
  merchant_negotiate   ← 상인 협상 (skip 가능)
  hero2_negotiate
  hero2_battle
  forge_open_2         ← 2차 제작 (선택, skip 가능)
  hero3_negotiate
  hero3_battle
  day_summary          ← 일일 요약. "다음 날" 버튼
```

day 5의 `day_summary` 후 → `game_over`.

### 2.1 state_machine 변경

- `PHASES`: 위 10개 + `game_over`
- `next_phase(current)`:
  - `day_summary` → 다음 날의 `forge_open` (단, day=5면 `game_over`)
  - 나머지는 단순 인덱스 +1
- `assert_phase(current, expected)`: 변경 없음
- 신규 `advance_to_next_day(player)`: day +1 + `current_phase = forge_open`. day=5에서 호출되면 `game_over`로 전환

### 2.2 skip 처리

`forge_open`, `forge_open_2`, `merchant_negotiate`는 사용자가 skip 가능. 새 엔드포인트:
- `POST /forge/skip`
- `POST /merchant/skip`

모두 phase만 advance.

---

## 3. 데이터 모델 변경

### 3.1 신규 테이블

```sql
create table if not exists merchants_today (
  id bigserial primary key,
  player_id bigint references players(id) on delete cascade,
  day int not null,
  materials jsonb not null,        -- [{material_id, qty, asking_price}]
  weapon jsonb,                    -- {asking_price, name, type, rarity, sharpness, ...} or null
  outcome text not null default 'pending' check (outcome in ('pending','done')),
  unique (player_id, day)
);

create table if not exists day_events (
  id bigserial primary key,
  player_id bigint references players(id) on delete cascade,
  day int not null,
  phase text not null,
  kind text not null,              -- 'forge'|'sale'|'reject_sell'|'battle'|'buy_materials'|'buy_weapon'|...
  payload jsonb not null,
  created_at timestamptz not null default now()
);
```

### 3.2 기존 테이블 확장

```sql
alter table heroes add column if not exists held_weapon_id bigint references weapons(id);
```
재방문 시 어떤 무기를 들고 왔는지 (Plan 3 강화 기반).

### 3.3 마이그레이션

`backend/migrations/002_daily_loop.sql` — 위 DDL + §6 RLS 정책.

---

## 4. 모듈 구성

### 4.1 백엔드

| 모듈 | 책임 | 상태 |
|---|---|---|
| `state_machine` | 10+1 phase 전환, `advance_to_next_day` | 변경 |
| `forge` | 동일 (skip 엔드포인트만 추가) | 변경 |
| `negotiation` | `step_buy()`, `finalize_buy()` 추가 | 변경 |
| `merchant` | 일일 인벤토리 생성, 카운터파티 응답 처리 | 신규 |
| `combat` | `roll_demon(day=N)`, prompt 강화 호출 | 변경 |
| `hero_registry` | `heroes_for_today()`, `schedule_return()` | 신규 |
| `day_summary` | 그 날의 `day_events` 집계 + 응답 빌드 | 신규 |
| `repo` | 신규 테이블 CRUD, return_day 기반 hero 조회 | 변경 |
| `api/forge.py` | phase 이름 `forge_open` / `forge_open_2` 둘 다 허용 + skip 엔드포인트 | 변경 |
| `api/negotiate.py` | hero1/2/3 협상 phase 모두 허용 | 변경 |
| `api/battle.py` | hero1/2/3 전투 phase 모두 허용 | 변경 |
| `api/merchant.py` | `POST /merchant/negotiate`, `/finalize`, `/skip` | 신규 |
| `api/day.py` | `GET /day/summary`, `POST /day/next` | 신규 |
| `api/state.py` | merchant 표시·hero history 일부 포함 | 변경 |

### 4.2 프론트엔드

| 컴포넌트 | 책임 | 상태 |
|---|---|---|
| `<DayRouter>` | 늘어난 phase에 맞춰 라우팅 | 변경 |
| `<SidePanel>` | 현재 day 표시 + 진행 phase 표시 | 변경 |
| `<ForgePanel>` | skip 버튼 추가 | 변경 |
| `<NegotiationChat>` | 변경 없음 (Plan 1과 동일) | — |
| `<MerchantPanel>` | 상인 인벤토리 + 다중 선택 + "협상" 버튼 + skip | 신규 |
| `<MerchantNegotiation>` | 묶음 가격 협상 채팅 (NegotiationChat 변형) | 신규 |
| `<DaySummary>` | day_events 리스트 + 평판·금화 변화 + "다음 날" | 신규 |
| `<GameOver>` | 5일 종료 후 최종 통계 + 새 게임 | 신규 |
| `<BattleResult>` | 변경 없음 | — |

### 4.3 협상 흐름 차이

| 항목 | 용사 (sell) | 상인 (buy) |
|---|---|---|
| 첫 가격 제시 | 플레이어 | 상인 (시세 기반) |
| 묶음 단위 | 무기 1개 | 재료 N개 + 무기 0~1개 |
| accept 시 처리 | 무기 owner 'sold' + 금화 ↑ + 평판 +1 | 인벤토리 추가 + 금화 ↓ + 평판 +1 |
| reject 시 처리 | 평판 -1 + 다음 phase | 평판 -1 (협상 후만, 즉시 거절은 0) + 다음 phase |

상인의 "즉시 거절 vs 협상 후 거절" 구분: `negotiations.rounds`가 비어 있으면 즉시 거절로 간주.

---

## 5. 데이터 플로우 — 하루 일과

```
GET /state → 현재 day, phase, 컨텍스트 객체 반환
POST /forge or /forge/skip → forge_open → hero1_negotiate
POST /negotiate (+/finalize | /player_accept | /player_reject) → hero1_negotiate → hero1_battle
POST /battle → hero1_battle → merchant_negotiate
POST /merchant/negotiate (+/finalize | /skip) → merchant_negotiate → hero2_negotiate
...
POST /battle (hero3) → hero3_battle → day_summary
GET /day/summary → 그 날의 이벤트·금화·평판·전투 결과 집계
POST /day/next → 다음 날의 forge_open (day=5면 game_over)
```

### 5.1 hero_registry 동작

`heroes_for_today(day)`:
- alive 용사 중 `return_day <= day`인 후보 우선 (우선순위 = 가장 오래 기다린 순)
- 부족하면 신규 hero를 LLM/랜덤으로 생성 (`api/game.py`의 hero 생성 로직 재사용 — 이름은 1~1000 숫자)
- 하루 3명 확정

`schedule_return(hero, battle_outcome, day)`:
- survived → `return_day = day + 3`
- fled → `return_day = day + 7`, `status = 'fled'` → alive로 전이 시점은 `return_day` 도래 시
- died → `status = 'dead'`, 재등장 없음

### 5.2 merchant 동작

`generate_today(day)`:
- `merchants_today.unique(player_id, day)`로 중복 방지
- `materials`: catalog에서 4~6종 랜덤 선택, qty 1~3, asking_price = base_price × random(1.0~1.5)
- weapon: 상인 인벤토리에는 무기 레코드 자체를 만들지 않고, `merchants_today.weapon_id`를 null로 두되 인벤토리 jsonb 내부에 `{"weapon": {asking_price, name, type, ...}}`로 시각화 정보만 저장. 플레이어가 구매 확정 시 비로소 `weapons` 행을 `owner='player'`로 insert. (이러면 weapons 테이블이 깨끗하고 owner enum 확장도 불필요.)
- 협상 결과 `outcome='done'` (수락이든 즉시거절이든)

---

## 6. 전투 강화 & RLS

### 6.1 battle.j2 프롬프트 보강

```jinja
... (기존)

전투 판정 지침 — 반드시 따를 것:
- 용사 전투력 = (근력 + 마력) × 1.0 + (무기 예리도 / 2 if 무기 있음 else 0)
- 적 위협력 = 난이도
- 전투력 ≥ 위협력 × 1.5 → 거의 항상 hero=survived + demon=killed, 무기는 preserved
- 전투력 ≈ 위협력 → hero가 survived 또는 injured 혼합, demon은 killed 또는 fled
- 전투력 ≪ 위협력 × 0.7 → hero가 injured 또는 died, demon이 survived 자주
- 무기 없으면 (맨손): 어떤 경우든 hero 부상·사망 확률 +30%, demon survived 확률 ↑
- 무기 예리도가 30 미만이면 weapon=destroyed 확률 ↑, 60 이상이면 거의 preserved
- 결과 코드는 위 기준을 일관되게 따르고, script는 그 결과를 자연스럽게 묘사
```

### 6.2 day 기반 demon 난이도

`combat.roll_demon(day, seed=None)`:

| day | 난이도 범위 |
|---|---|
| 1 | 1 ~ 10 |
| 2 | 3 ~ 15 |
| 3 | 8 ~ 22 |
| 4 | 14 ~ 30 |
| 5 | 20 ~ 40 |

DEMONS 풀(고블린·임프·작은 영혼·지옥개) 그대로. type만 난이도 범위 안에서 가능한 것 중 랜덤.

### 6.3 RLS

`002_daily_loop.sql` 끝에:

```sql
alter table players          enable row level security;
alter table inventory        enable row level security;
alter table weapons          enable row level security;
alter table heroes           enable row level security;
alter table negotiations     enable row level security;
alter table battles          enable row level security;
alter table merchants_today  enable row level security;
alter table day_events       enable row level security;
alter table materials        enable row level security;

create policy "materials_anon_read"
  on materials for select to anon using (true);
```

service_role은 RLS bypass라 백엔드는 정상 동작. anon은 materials read만.

---

## 7. 에러 처리 & 엣지 케이스

### 7.1 새 케이스

| 상황 | 처리 |
|---|---|
| `merchant_negotiate` 진입했는데 `merchants_today` 행 없음 | `merchant.generate_today` 자동 호출 |
| `day_summary` 에서 "다음 날" 더블 클릭 | day가 이미 advance됐으면 동일 응답 (idempotent — 새 phase가 forge_open이면 그대로 반환) |
| hero pool에 alive 후보 0명인데 신규 생성도 실패 | 500 + `no_hero_available`. 실제로는 항상 신규 생성 가능 |
| 상인 무기를 사서 진열장에 넣고 같은 날 다른 용사에게 팔기 | 정상 동작 (소유자 player → sold 전환) |
| 묶음 구매 가격이 보유 금화 초과 | 400 + `insufficient_gold` |

### 7.2 기존 처리는 그대로

LLM 응답 신뢰하지 않음, JSON 파싱 실패 시 폴백, 잘못된 phase 시 400 — Plan 1과 동일.

---

## 8. 테스트 전략

### 8.1 단위 테스트 (pytest)

- `state_machine.next_phase` — 10+1 phase 순서, day 전이, game_over 진입
- `state_machine.advance_to_next_day` — day +1 + reset, day=5 시 game_over
- `combat.roll_demon(day=N)` — day별 난이도 범위가 표 안에 들어옴 (시드 다수)
- `merchant.generate_today` — 시드 고정 시 결정성, 재료 4~6종 + 무기 1개
- `negotiation.step_buy` — 픽스처 모드로 accept/counter/reject 분기 검증
- `negotiation.finalize_buy` — 인벤토리 추가·금화 차감·평판 변화
- `hero_registry.heroes_for_today` — return_day 우선·부족 시 신규 생성
- `hero_registry.schedule_return` — 결과별 return_day 계산
- `day_summary.build` — events 집계 카운트

### 8.2 새 LLM 픽스처

`negotiate_buy_accept.json`, `negotiate_buy_counter.json`, `negotiate_buy_reject.json`.

### 8.3 통합 테스트

기존 `test_integration_slice.py` 옆에 `test_integration_day.py` 추가. **하루 전체 골든 패스** 검증:

```
forge → hero1 (sell accept) → battle → merchant (buy accept) →
hero2 (sell reject) → battle (맨손) → forge_2 → hero3 (counter→accept) → battle →
day_summary → 다음 날 진입
```

FakeRepo에 신규 테이블·메서드 추가.

5일 풀 시뮬레이션은 자동화하지 않음 (수동 검증 체크리스트).

### 8.4 프론트엔드

`tsc --noEmit` + 수동 골든 패스 (5일 풀 플레이).

### 8.5 RLS 수동 검증

Supabase SQL Editor에서:
```sql
-- anon 키로 (Settings → API → anon)
select count(*) from players;     -- 0 기대
select count(*) from materials;   -- 20 기대
```

---

## 9. 디렉토리 변경 요약

```
backend/
├── app/
│   ├── merchant.py            (신규)
│   ├── hero_registry.py       (신규)
│   ├── day_summary.py         (신규)
│   ├── state_machine.py       (변경)
│   ├── combat.py              (변경)
│   ├── negotiation.py         (변경)
│   ├── repo.py                (변경)
│   ├── llm/prompts/
│   │   ├── battle.j2          (변경 — 판정 지침 추가)
│   │   └── negotiate_buy.j2   (신규)
│   └── api/
│       ├── merchant.py        (신규)
│       ├── day.py             (신규)
│       ├── forge.py           (변경 — skip 엔드포인트)
│       ├── negotiate.py       (변경)
│       ├── battle.py          (변경)
│       └── state.py           (변경)
├── migrations/
│   └── 002_daily_loop.sql     (신규)
└── tests/
    ├── test_state_machine.py  (변경)
    ├── test_combat.py         (변경)
    ├── test_merchant.py       (신규)
    ├── test_negotiation.py    (변경 — step_buy)
    ├── test_hero_registry.py  (신규)
    ├── test_day_summary.py    (신규)
    ├── test_integration_day.py (신규)
    └── fixtures/llm/
        ├── negotiate_buy_accept.json   (신규)
        ├── negotiate_buy_counter.json  (신규)
        └── negotiate_buy_reject.json   (신규)

frontend/src/components/
├── DayRouter.tsx              (변경)
├── SidePanel.tsx              (변경)
├── ForgePanel.tsx             (변경 — skip)
├── MerchantPanel.tsx          (신규)
├── MerchantNegotiation.tsx    (신규)
├── DaySummary.tsx             (신규)
└── GameOver.tsx               (신규)
```

---

## 10. 열린 결정 (구현 시점에 정함)

- 상인 신규 무기 생성 시 LLM 호출 여부: 매일 LLM 호출은 비용·시간 부담. 대안 — 미리 시드된 상인 무기 풀(20개)에서 매일 1개 뽑기.
- 상인 NPC 캐릭터(이름·성격) 매일 고정 vs 매일 새로?: MVP는 매일 새로 (이름은 hero처럼 숫자 1~1000).
- `<DaySummary>` 의 시각화: 단순 리스트 vs 차트. MVP는 리스트.
- 상인 인벤토리에 같은 재료 종 중복 허용 vs 종당 1행: 종당 1행 추천 (qty로 처리).
- battle 프롬프트의 "수치 기반 가이드"가 LLM 출력에 잘 반영되는지 — 실제 호출로 검증 필요. 결과 코드의 통계가 기대를 벗어나면 프롬프트 추가 튜닝.

# 비동기 전투 + 가변 하루 길이 — 설계

작성일: 2026-05-28
관련 피드백: `docs/feedback/0527.txt` 항목 #1, #2 (1차 배치)

## 배경

기존 게임은 하루에 신규 용사 3명 + 상인 1명이 고정 순서로 방문하고, 협상 직후 동기적으로 전투가 해결되어 결과가 즉시 표시된다. 피드백 #1, #2에 따라:

- **전투는 비동기**: 용사가 떠난 뒤 며칠 후에 결과가 통보된다. 사망은 우편, 생존/부상은 재방문 시점에 노출.
- **하루 길이는 가변**: 평판에 따라 방문자 수가 달라진다.

이 두 변경은 `state_machine.PHASES`의 고정 9-phase 구조를 갈아엎어야 하므로 한 묶음으로 진행한다.

## 합의된 결정

1. **방문자 슬롯 추상화** — `VisitorKind = new_hero | returning_hero | merchant` (3차 배치에서 `mission_npc` 추가).
2. **하루 시작 시 스케줄 큐 생성** — forge_open 진입 시점에 그 날 방문자 시퀀스를 결정해 `players.day_schedule` JSONB에 저장. 이후엔 인덱스만 증가.
3. **outcome 즉시 결정, 통보만 지연** — 협상 수락 시점에 `combat.decide_outcomes`로 결과 확정 → `pending_outcomes` 테이블에 `resolve_day`와 함께 저장. 결정성 시드 유지.
4. **결과 노출 채널** — 사망만 아침 우편 모달, 생존/부상은 재방문 슬롯 자체가 통지.
5. **하루 phase 단순화** — `forge_open → visitor → day_summary`. 방문자 종류별 분기는 프론트가 `current_visitor.kind`로 처리.
6. **상인 1회 보장** — 평판 슬롯과 별개로 하루 1명 고정. 위치는 시드로 결정.
7. **재방문 우선 배치** — 재방문 예정 용사가 평판 슬롯을 우선 점유, 남는 자리에 신규. 슬롯 초과분은 `resolve_day += 1`로 미룸.
8. **무기는 출정 즉시 인벤토리에서 제거** — `weapon_snapshot`이 `pending_outcomes`에 박제됨.

## 평판 → 용사 슬롯 수

| 평판 | 용사 수 |
|---|---|
| 0–10 | 3 (고정) |
| 11–20 | 3–5 (랜덤) |
| 21–40 | 5–7 |
| 41–60 | 8–10 |
| 61+ | 10 (고정) |

총 슬롯 = 용사 수 + 상인 1. 상인 위치는 용사 슬롯이 N명일 때 `[0, N]` 범위에서 `seed % (N+1)`로 결정해 해당 인덱스에 insert (0이면 맨 앞, N이면 맨 뒤).

## 재방문/우편 타이밍 (depart_day = d)

| 결과 | 통보 시점 |
|---|---|
| 생존 (survive) | `d + rand_in([2,3], seed+1)` 아침 재방문 슬롯 |
| 부상 (injure)  | `d + rand_in([5,7], seed+2)` 아침 재방문 슬롯 |
| 사망 (die)     | `d + rand_in([1,2], seed+3)` 아침 우편 모달 |

## 데이터 모델 (마이그레이션 009)

### players 컬럼 추가
- `day_schedule JSONB NOT NULL DEFAULT '[]'`
- `current_visitor_index INT NOT NULL DEFAULT 0`

스케줄 entry 예시:
```json
[
  {"kind":"returning_hero","hero_id":"uuid","outcome_id":"uuid"},
  {"kind":"new_hero","hero_id":"uuid"},
  {"kind":"merchant"},
  {"kind":"new_hero","hero_id":"uuid"}
]
```

### 새 테이블 `pending_outcomes`
```sql
id              UUID PK
player_id       UUID FK
hero_id         UUID FK
depart_day      INT
resolve_day     INT
kind            TEXT CHECK IN ('revisit_survive','revisit_injure','death_mail')
outcome_json    JSONB        -- 잡은 몹 수, 무기 파손 여부, 용사 의견 등
weapon_snapshot JSONB        -- 떠날 때의 무기 데이터 (이름, 칭호, 스탯)
consumed        BOOL DEFAULT FALSE
created_at      TIMESTAMP
```

처리되면 `consumed=TRUE`. forge_open에서 "오늘 resolve될" 조회 = `resolve_day = current_day AND consumed = FALSE`.

### 변하지 않는 것
- `weapons`: 출정 시 그냥 DELETE. 정보는 `weapon_snapshot`에 박제됨.
- `heroes`: 동일 hero_id 재사용. 페르소나는 deterministic 시드로 재현 가능.

## 하루 진행 로직

### `forge_open` 진입 시 (= 새 날 시작 직후)
1. `pending_outcomes`에서 `resolve_day == current_day AND consumed == FALSE` 조회.
2. `kind == "death_mail"` → `state.death_mails`로 클라이언트에 노출. 모달 ack 시 `POST /mail/{id}/ack` → consumed.
3. `kind == "revisit_*"` → 다음 스케줄 생성 단계에서 재방문 슬롯으로 박힘.
4. **스케줄 생성** (deterministic):
   - 평판 → 용사 슬롯 수 N (위 표). 랜덤 구간은 `seed = player_id*1_000_003 + day*31 + 11`로 결정.
   - 재방문 슬롯 먼저 채움. N 초과분은 잘림 → `resolve_day += 1`로 업데이트 (consumed 유지 FALSE).
   - 남은 자리에 신규 용사 `hero_registry.heroes_for_today`로 채움 (기존 시드 그대로).
   - 상인 위치 = `seed % (len+1)`로 결정 후 해당 위치에 insert.
5. `day_schedule` 저장, `current_visitor_index = 0`.

### Phase 전이
```
forge_open --POST /day/forge/done--> visitor
visitor    --(슬롯 모두 처리됨)-->   day_summary
day_summary --POST /day/next-->     forge_open (current_day++)
```

### 엔드포인트
- `GET /state` — 응답에 `current_visitor: {kind, ...}` 와 `death_mails: [...]` 포함.
- `POST /visitor/current/negotiate` (kind=new_hero|returning_hero)
- `POST /visitor/current/merchant/buy` (kind=merchant)
- `POST /visitor/current/return` (kind=returning_hero, "보내기")
- `POST /mail/{id}/ack`
- 모든 슬롯 처리 엔드포인트는 내부적으로 `current_visitor_index++`, 마지막이면 phase 전이.

### 제거되는 엔드포인트
- `POST /hero/{slot}/negotiate`, `POST /hero/{slot}/battle` 등 slot 기반 전부.

## 비동기 전투 해결

협상 수락 시점 (`POST /visitor/current/negotiate` accept 분기) 처리:

1. 기존 거래 처리 (골드 이동).
2. `combat.decide_outcomes` 즉시 호출 — 시드 = `player_id*1_000_003 + depart_day*31 + hero_id_hash + 13`.
   - 결과: `survive | injure | die`, 잡은 몹 수, 무기 파손 여부, 용사 의견 (`want_better_weapon | weapon_broke | none`).
3. resolve_day 계산 (위 표).
4. `pending_outcomes` insert. weapon row DELETE.
5. **엔딩 감지** 호출 — 기존 `combat.run_battle` 안에 있던 `endgame.detect_ending`을 여기로 이동. `surt_killed/youth_blood/weapons_broken` 모두 outcome 기반이라 호환.
6. 슬롯 advance.

### LLM 사용
- 협상 narration은 기존과 동일 (즉시 호출).
- 전투 narration은 **재방문 시점**에 LLM이 `outcome_json`을 받아 "지난 며칠간 어떻게 싸웠는지" 회고 형식으로 생성.
- 출정 즉시는 LLM 호출 없음 — 정적 텍스트 "출정했다."

### 재방문 슬롯 처리 (1차 배치 범위)
- 회고 LLM narration 표시 + "보내기" 버튼만.
- `pending_outcome.consumed = TRUE`, advance.
- 전리품 거래는 stub (2차 배치에서 구현).

## 프론트엔드 변화

- `DayRouter.tsx` — phase 3개로 분기 단순화.
- 신규 `VisitorRouter` — `current_visitor.kind`로 분기:
  - `new_hero` → 기존 `HeroNegotiatePanel` 재사용 (slot prop 제거)
  - `returning_hero` → 신규 `ReturningHeroPanel`
  - `merchant` → 기존 `MerchantPanel` 재사용
- App 레벨에서 `state.death_mails` 비어있지 않으면 순차 모달.
- 제거: hero1/2/3 슬롯 라우팅, "다음 영웅" 버튼.

## 테스트

기존 144개 중 hero-slot phase에 의존하는 테스트 다수 깨짐 → visitor-index 기반으로 재작성. `FakeRepo`에 `pending_outcomes` CRUD 추가.

신규 테스트:
- `test_day_schedule`: 평판 구간별 슬롯 수, 시드 재현성, 재방문 우선 배치, 상인 1명 보장, 슬롯 초과 시 resolve_day 미루기.
- `test_pending_outcomes`: outcome 결정 결정성, resolve_day 범위, weapon_snapshot 보존.
- `test_async_combat`: 협상 수락 → DB outcome 박힘, weapon DELETE, 슬롯 advance.
- `test_death_mail`: forge_open 진입 시 모달 데이터 노출, ack 후 consumed.
- `test_endgame_relocation`: 엔딩 감지가 outcome 결정 시점에서 발동.

## 마이그레이션 (`009_async_combat.sql`)

- `players` 컬럼 3개 추가, `pending_outcomes` 테이블 생성.
- 기존 데이터 처리: 진행 중 게임의 `current_phase`를 강제로 `forge_open`으로 리셋 (`current_day` 유지). 다음 forge_open 진입 시 스케줄이 자연스럽게 재생성됨.

## 롤아웃 순서

1. 마이그레이션 009 + FakeRepo 확장.
2. `day_schedule` 생성 로직 + 테스트.
3. `pending_outcomes` + outcome 결정 + 비동기 흐름 + 테스트.
4. 엔드포인트 통합 (`/visitor/current/...`).
5. 프론트 라우터/패널 교체.
6. 죽음 우편 모달.
7. 전체 회귀 테스트.

## 범위 밖 (명시적 OUT)

- 전리품 거래 (2차 배치)
- chitchat (2차 배치)
- 협상 인내심 (2차 배치)
- 부상 시 무기 반환/수리 흐름 (2차 배치에서 결정)
- 미션 NPC, 세금관, 상인조합장 (3차 배치)
- 상인 재료 진행도 (4차 배치)
- 무기 칭호 (4차 배치)

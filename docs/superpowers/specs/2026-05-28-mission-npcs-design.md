# 미션 NPC 시스템 — 설계 (3차 배치)

작성일: 2026-05-28
관련 피드백: `docs/feedback/0527.txt` 항목 #7
선행: 1차(비동기 전투/가변 하루), 2차(전리품/chitchat/인내심)

## 배경

피드백 #7: "중간중간 해결해 나가야 하는 작은 미션들. 실패 시 game over." 두 예시:
- **세금관**: 10일마다 1000골드 세금. 3일차 예고, 10/20/30/...에 징수. 협상 없음.
- **상인조합장**: 11~15일 사이 랜덤 등장 + d+3 안에 평판 50 도달. 달성 시 재등장 칭찬, 실패 시 game over.

두 미션이 패턴이 달라(반복 vs 1회성·조건부) 일반 인프라가 필요하다.

## 합의된 결정

1. **방문자 슬롯에 새 kind `mission_npc`** — 모달이 아니라 day_schedule 큐에 끼우는 형식.
2. **이번 배치 범위 = 프레임워크 + 두 미션 다 구현**.
3. **새 테이블 `missions`** — 인스턴스 단위 행 저장 (kind/phase/due_day/status/payload).
4. **lazy 스케줄링** — forge_open 진입 시 `missions.scheduler.advance()`가 plan + evaluate.
5. **실패 = 기존 endgame 시스템 + 새 ending_kind** (`mission_tax_unpaid`, `mission_league_failed`).
6. **세금 = 단순**: 1000 고정, 협상X, 부족하면 즉시 ending.
7. **상인조합장 = 단순**: 평판 50 임계 고정, 즉시 성공 처리 가능.

## 데이터 모델 (마이그레이션 012)

```sql
CREATE TABLE IF NOT EXISTS missions (
  id         BIGSERIAL PRIMARY KEY,
  player_id  BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
  kind       TEXT NOT NULL,           -- 'tax', 'league_chief'
  phase      TEXT NOT NULL,           -- 'warning', 'collect', 'challenge', 'praise'
  due_day    INT NOT NULL,
  status     TEXT NOT NULL DEFAULT 'pending',  -- pending → done | failed | condition_met
  payload    JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  done_at    TIMESTAMPTZ,
  UNIQUE (player_id, kind, due_day, phase)
);
CREATE INDEX IF NOT EXISTS idx_missions_player_status
  ON missions(player_id, status, due_day);
```

`players.ending_kind`에 새 문자열 두 종류 (`mission_tax_unpaid`, `mission_league_failed`) — 별도 enum 변경 없음 (현재 TEXT).

## 모듈 구조

```
backend/app/missions/
  __init__.py         # MissionModule 인터페이스 + 레지스트리
  scheduler.py        # advance(player), today_slots(...)
  tax.py              # 세금관
  league_chief.py     # 상인조합장
```

**MissionModule 인터페이스** (각 미션 모듈이 노출):
```python
def plan(player: dict, day: int) -> list[dict]:
    """오늘 insert해야 할 새 미션 행들. 멱등."""

def evaluate(player: dict, day: int, mission: dict) -> tuple[str, str | None]:
    """pending 미션 평가. returns (new_status, ending_kind_or_None).
    new_status in {'pending', 'done', 'failed', 'condition_met'}."""

def slot_for(mission: dict) -> dict:
    """day_schedule entry. 슬롯에 표시될 phase별 payload 포함."""

def on_action(player: dict, mission: dict, action: str) -> dict:
    """슬롯 액션 처리 — pay/ack/skip. side effects + status 갱신."""
```

레지스트리는 `__init__.py`의 dict `MODULES = {"tax": tax, "league_chief": league_chief}`.

## 스케줄러 (`missions/scheduler.py`)

`advance(player)` 흐름 — forge_open 진입 시 호출:

1. **Plan**: 각 모듈의 `plan(player, day)` 호출 → 신규 미션 행 insert (UNIQUE로 멱등).
2. **Evaluate**: 모든 pending 미션 조회 → 모듈별 `evaluate()` 호출 → status 전이, ending 트리거.
   - ending 발생 시 `endgame.apply_ending(player_id, kind)` 즉시 호출, advance 종료.
3. **Follow-up plan**: condition_met 같은 중간 status가 새 phase 미션을 만드는 경우 다시 plan 호출 (단, 1회만 — 무한 재귀 방지).

`today_slots(player_id, day) -> list[dict]`:
- `kind=mission_npc` 슬롯들. status=pending이고 due_day=today인 미션을 모듈별 `slot_for()`로 변환.

## 세금관 (`missions/tax.py`)

**plan**:
- `day == 3` → warning 미션 insert: `{kind:tax, phase:warning, due_day:3, payload:{}}`
- `day in {10, 20, 30, 40, 50, 60, 70, 80, 90}` → collect 미션 insert: `{kind:tax, phase:collect, due_day:day, payload:{amount:1000}}`

**evaluate**:
- warning: status를 done으로 두지 않음 (advance/skip이 슬롯 처리에서 마무리). 만기일이 지나도 fail 아님 (정보 전달만).
- collect: due_day < current_day && status == pending → fail + ending=`mission_tax_unpaid`.

**slot_for**:
```json
{"kind":"mission_npc", "mission_id":7, "mission_kind":"tax",
 "phase":"warning"|"collect", "amount":1000}
```

**on_action**:
- warning: action=`ack` → status=done.
- collect, action=`pay`: `player.gold >= 1000` 검증, 부족하면 ValueError. 차감 + status=done. day_event `tax_paid` 기록.
- collect, action=`skip`: status=failed + ending=`mission_tax_unpaid`.
- collect, action=`ack`: 의미 없음, 액션 거절 (400).

## 상인조합장 (`missions/league_chief.py`)

**spawn_day 결정**: `rand_in([11,15], seed=(player_id*1_000_003 + 47) & 0xFFFFFFFF)` — 플레이어별 결정성.

**plan**:
- `day == spawn_day` → challenge 미션 insert: `{kind:league_chief, phase:challenge, due_day:day, payload:{threshold:50, deadline:day+3}}`.
- praise는 evaluate 단계에서 트리거 (다음 절).

**evaluate**:
- challenge, status=pending:
  - `player.reputation >= 50` → status=`condition_met`, 동시에 praise 미션 insert: `{kind:league_chief, phase:praise, due_day:current_day+1, payload:{}}`.
  - else `current_day > deadline` → status=failed + ending=`mission_league_failed`.
  - else 그대로 둠.
- challenge, status=condition_met → 다음 forge_open에서 다시 advance가 부르겠지만 추가 작업 없음.
- praise: 만기 후 미처리면 그냥 done (조용히 지나감, fail 아님).

**slot_for**:
- challenge phase 슬롯은 spawn_day 당일에만 등장 (이후 status는 pending이지만 due_day가 지나 today_slots에 안 잡힘).
  - 단, **챌린지가 player가 미리 평판 50 달성한 상태로 spawn_day에 등장**할 수도 있음. 이 경우 evaluate가 condition_met 처리 후 praise insert. spawn_day 슬롯에는 challenge phase로 등장 (도전장 + 칭찬은 다음날).
- praise phase 슬롯은 `due_day == current_day` (그 다음 forge_open).

**on_action**:
- challenge action=`ack` → 그대로 (status 유지 pending — evaluate가 조건 평가).
- praise action=`ack` → status=done.

## 슬롯 통합

**`day_open.prepare_day` 변경**:
1. 기존: pending_outcomes 조회.
2. **신규**: `missions.scheduler.advance(player)` — plan/evaluate/endgame 트리거.
3. ending이 발동했으면 schedule 만들지 않고 리턴 (game_over phase로 진행).
4. **`missions.scheduler.today_slots(player_id, day)`** → 미션 슬롯 리스트.
5. 평판 → 용사 슬롯 수 N, 재방문 우선, 신규 채움, 상인 1개 끼움.
6. **미션 슬롯은 최종 schedule의 맨 앞에 prepend** (그 날 첫 사건).
7. 저장.

## API

**신규 엔드포인트** `POST /visitor/current/mission_action`:
- body: `{action: "pay" | "ack" | "skip"}`
- 검증: phase=visitor, current slot kind=`mission_npc`.
- 미션 모듈 `on_action` 호출. ValueError → 400.
- 슬롯 advance (`/visitor/current/skip`와 동일 advance 로직).

**`/visitor/current/skip`** — mission_npc 슬롯이면 `on_action(action="skip")` 거쳐서 처리 (세금 collect skip = fail).

**`/state`** — 슬롯 hydration에 `mission_kind`, `phase`, `amount`, `threshold`, `deadline`을 그대로 펼침.

## 프론트엔드

**`VisitorRouter`** 분기 추가: `v.kind === "mission_npc"` → `MissionPanel`.

**`MissionPanel`** (신규):
- 슬롯 정보를 받아 mission_kind+phase에 따라 제목/메시지/액션 버튼 렌더.
- 메시지·버튼은 `frontend/src/missions.ts`의 매핑 상수에서 가져옴.

**메시지/버튼 매핑** (`missions.ts`):
- `tax.warning`: 메시지 "이 마을은 세금을 매기지! 10일 뒤 다시 와서 1000골드 받아간다, 그때 안 내면 알지?" / 버튼 [알겠다(action=ack)]
- `tax.collect`: "오늘이 그날이다. 1000골드 내놔라." / 버튼 [1000골드 상납하기(pay, disabled if gold<1000)] [도망간다(skip)]
- `league_chief.challenge`: "한자 상인조합장이다. 우리 도시에서 장사하려면 평판 50은 찍어야지. 3일 안에 못 보이면 가게 닫게 만들 거다." / 버튼 [알겠다(ack)]
- `league_chief.praise`: "고생했다, 대장장이. 인정해주마. 잘 해 봐라." / 버튼 [알겠다(ack)]

**`endings.ts`** 추가:
- `mission_tax_unpaid` — "세금 미납으로 마을에서 쫓겨났다"
- `mission_league_failed` — "상인조합장의 인정을 못 받아 가게가 강제 폐업"

**API 래퍼** (`api.ts`):
- `visitorMissionAction(action: "pay"|"ack"|"skip")` → POST `/visitor/current/mission_action` body `{action}`

## 테스트

신규:
- `test_mission_tax.py`: plan 멱등, warning/collect 분기, pay 성공/실패, fail 시 ending
- `test_mission_league_chief.py`: spawn_day 결정성, challenge insert, 평판 50 도달 → condition_met + praise insert, deadline 초과 → fail
- `test_mission_scheduler.py`: plan+evaluate+today_slots 통합
- `test_day_open_with_missions.py`: prepare_day에 mission 슬롯 prepend
- `test_api_mission_action.py`: /visitor/current/mission_action 통합

기존 보완:
- `test_day_open.py` — mission 슬롯 통합 후에도 일반 슬롯이 정상 동작

## 마이그레이션 적용

Supabase MCP `apply_migration` 또는 Studio SQL Editor로 012 적용. 기존 진행 중 게임은 다음 forge_open에서 자동으로 missions 채워짐. day 3 이미 지난 게임은 warning 스킵, 다음 collect (day 10/20/...)에서 정상 등장.

## 롤아웃 순서

1. 마이그레이션 012 + FakeRepo 확장 (missions CRUD)
2. `repo.py` missions CRUD 추가
3. `missions/__init__.py` 인터페이스 + 레지스트리
4. `missions/tax.py` + 테스트
5. `missions/league_chief.py` + 테스트
6. `missions/scheduler.py` + 테스트
7. `day_open.prepare_day` 통합 + 테스트
8. `endgame`에 새 ending kind 등록
9. `/visitor/current/mission_action` 엔드포인트 + 테스트
10. `/state` 슬롯 hydration에 mission payload 노출
11. 프론트 `MissionPanel`, `endings.ts`, api 래퍼, `VisitorRouter` 분기
12. 회귀 + 수동 검증

## 범위 밖 (명시적 OUT)

- 추가 미션 (왕실 보급관, 길드 의뢰 등)
- 미션 보상 시스템 (현재는 회피 = 보상)
- 미션 알림/캘린더 사이드 UI
- 4차 배치 항목 (상인 재료 진행도, 무기 칭호)

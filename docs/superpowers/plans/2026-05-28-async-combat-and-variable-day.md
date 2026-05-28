# 비동기 전투 + 가변 하루 길이 — 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 비동기 전투 해결과 평판 기반 가변 방문자 수를 도입해, 고정 9-phase 하루 루프를 `forge_open → visitor → day_summary` + 동적 스케줄 큐로 교체한다.

**Architecture:** 하루 시작 시 `forge_open`에서 평판 + pending 재방문을 모아 `day_schedule` JSONB 큐를 결정성 시드로 생성. 각 슬롯은 `VisitorKind` (`new_hero` / `returning_hero` / `merchant`)별로 프론트가 분기. 협상 수락 시 서버가 `combat.decide_outcomes`로 결과를 즉시 확정해 `pending_outcomes` 테이블에 박고 (`resolve_day` 포함), 무기는 DELETE. resolve_day가 되면 사망은 우편 모달, 생존/부상은 재방문 슬롯으로 자동 노출.

**Tech Stack:** Python 3.12 + FastAPI + Supabase (Postgres) + Pytest, React 18 + TypeScript + Vite.

**Spec:** `docs/superpowers/specs/2026-05-28-async-combat-and-variable-day-design.md`

---

## File Structure

**Backend — create**
- `backend/migrations/009_async_combat.sql` — 스키마 마이그레이션
- `backend/app/scheduler.py` — 하루 방문자 스케줄 생성 (결정성 시드)
- `backend/app/pending_outcomes.py` — outcome 결정 + resolve_day 계산
- `backend/app/api/visitor.py` — 통합 visitor 엔드포인트
- `backend/app/api/mail.py` — 우편 ack
- `backend/tests/test_scheduler.py`
- `backend/tests/test_pending_outcomes.py`
- `backend/tests/test_async_combat_flow.py`
- `backend/tests/test_visitor_endpoints.py`
- `backend/tests/test_death_mail.py`

**Backend — modify**
- `backend/app/state_machine.py` — PHASES 축소, `advance_visitor` 추가
- `backend/app/repo.py` — `pending_outcomes` CRUD + `day_schedule` 헬퍼 + DELETE weapon
- `backend/app/combat.py` — `decide_outcomes`가 `hero_opinion` 반환, `run_battle` 제거(혹은 thin wrapper)
- `backend/app/endgame.py` — outcome 기반 호출부 확인 (변경 없을 수도)
- `backend/app/api/__init__.py` — visitor/mail 라우터 등록, deprecated 라우터 제거
- `backend/app/api/state.py` — `current_visitor`, `death_mails` 응답에 포함
- `backend/app/api/day.py` — `/day/next` advance_to_next_day 호환
- `backend/app/main.py` — 라우터 wiring
- `backend/tests/conftest.py` — FakeRepo 확장
- 다수의 기존 테스트 (`test_state_machine.py`, `test_integration_day.py`, `test_combat.py`, `test_negotiation.py` 등) — visitor 인덱스 모델로 재작성

**Frontend — create**
- `frontend/src/components/VisitorRouter.tsx`
- `frontend/src/components/ReturningHeroPanel.tsx`
- `frontend/src/components/DeathMailModal.tsx`

**Frontend — modify**
- `frontend/src/types.ts` — `VisitorKind`, `CurrentVisitor`, `DeathMail` 추가
- `frontend/src/api.ts` — `/visitor/current/...`, `/mail/{id}/ack` 래퍼
- `frontend/src/components/DayRouter.tsx` — phase 3개로 단순화
- `frontend/src/components/NegotiationChat.tsx` — slot prop 제거
- `frontend/src/components/MerchantPanel.tsx` — slot prop 제거
- `frontend/src/App.tsx` — DeathMailModal 마운트

---

### Task 1: 마이그레이션 009 — 스키마 추가

**Files:**
- Create: `backend/migrations/009_async_combat.sql`

- [ ] **Step 1: 마이그레이션 SQL 작성**

```sql
-- 009_async_combat.sql
-- 비동기 전투 + 가변 하루 길이 지원

-- 1) players 컬럼 추가
ALTER TABLE players
  ADD COLUMN IF NOT EXISTS day_schedule JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS current_visitor_index INT NOT NULL DEFAULT 0;

-- 2) pending_outcomes 테이블
CREATE TABLE IF NOT EXISTS pending_outcomes (
  id              BIGSERIAL PRIMARY KEY,
  player_id       BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
  hero_id         BIGINT NOT NULL REFERENCES heroes(id) ON DELETE CASCADE,
  depart_day      INT NOT NULL,
  resolve_day     INT NOT NULL,
  kind            TEXT NOT NULL CHECK (kind IN ('revisit_survive','revisit_injure','death_mail')),
  outcome_json    JSONB NOT NULL DEFAULT '{}'::jsonb,
  weapon_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
  consumed        BOOLEAN NOT NULL DEFAULT FALSE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pending_outcomes_player_resolve
  ON pending_outcomes(player_id, resolve_day, consumed);

-- 3) 기존 진행 중 게임의 phase 정규화
UPDATE players
  SET current_phase = 'forge_open',
      current_visitor_index = 0,
      day_schedule = '[]'::jsonb
  WHERE current_phase NOT IN ('forge_open', 'visitor', 'day_summary', 'game_over');
```

- [ ] **Step 2: Commit**

```bash
git add backend/migrations/009_async_combat.sql
git commit -m "migrate: 009 add day_schedule, current_visitor_index, pending_outcomes"
```

---

### Task 2: FakeRepo 확장 — pending_outcomes + day_schedule

**Files:**
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: FakeRepo 확인**

Run: `grep -n "class FakeRepo" backend/tests/conftest.py`

기존 FakeRepo 클래스 구조를 확인한다. `players` dict와 `weapons`, `heroes` 리스트가 있을 것이다.

- [ ] **Step 2: pending_outcomes 저장소 + 메서드 추가**

`conftest.py`의 FakeRepo 클래스에 다음을 추가:

```python
# __init__ 에 추가
self.pending_outcomes: list[dict] = []
self._pending_seq = 0

# 메서드 추가
def insert_pending_outcome(self, row: dict) -> dict:
    self._pending_seq += 1
    saved = {"id": self._pending_seq, "consumed": False, **row}
    self.pending_outcomes.append(saved)
    return saved

def list_pending_to_resolve(self, player_id: int, day: int) -> list[dict]:
    return [
        p for p in self.pending_outcomes
        if p["player_id"] == player_id
        and p["resolve_day"] == day
        and not p["consumed"]
    ]

def mark_pending_consumed(self, outcome_id: int) -> None:
    for p in self.pending_outcomes:
        if p["id"] == outcome_id:
            p["consumed"] = True
            return

def update_pending_resolve_day(self, outcome_id: int, new_day: int) -> None:
    for p in self.pending_outcomes:
        if p["id"] == outcome_id:
            p["resolve_day"] = new_day
            return

def get_pending(self, outcome_id: int) -> dict | None:
    for p in self.pending_outcomes:
        if p["id"] == outcome_id:
            return p
    return None

def delete_weapon(self, weapon_id: int) -> None:
    self.weapons = [w for w in self.weapons if w["id"] != weapon_id]
```

또한 `_player_defaults`에 `day_schedule=[], current_visitor_index=0` 추가.

- [ ] **Step 3: 테스트 fixture 호환 확인**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_repo_multi.py -v`
Expected: PASS (기존 테스트는 새 필드를 보지 않음).

- [ ] **Step 4: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "test: extend FakeRepo with pending_outcomes + day_schedule"
```

---

### Task 3: repo.py — pending_outcomes CRUD + weapon DELETE + day_schedule 헬퍼

**Files:**
- Modify: `backend/app/repo.py`

- [ ] **Step 1: 함수 추가**

`backend/app/repo.py` 맨 아래에 append:

```python
# --- 009: pending_outcomes ---

def insert_pending_outcome(row: dict[str, Any]) -> dict[str, Any]:
    return _client().table("pending_outcomes").insert(row).execute().data[0]


def list_pending_to_resolve(player_id: int, day: int) -> list[dict[str, Any]]:
    return _client().table("pending_outcomes").select("*") \
        .eq("player_id", player_id).eq("resolve_day", day).eq("consumed", False) \
        .order("id").execute().data


def mark_pending_consumed(outcome_id: int) -> None:
    _client().table("pending_outcomes").update({"consumed": True}) \
        .eq("id", outcome_id).execute()


def update_pending_resolve_day(outcome_id: int, new_day: int) -> None:
    _client().table("pending_outcomes").update({"resolve_day": new_day}) \
        .eq("id", outcome_id).execute()


def get_pending(outcome_id: int) -> dict[str, Any] | None:
    rows = _client().table("pending_outcomes").select("*") \
        .eq("id", outcome_id).limit(1).execute().data
    return rows[0] if rows else None


def delete_weapon(weapon_id: int) -> None:
    _client().table("weapons").delete().eq("id", weapon_id).execute()
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/repo.py
git commit -m "repo: add pending_outcomes CRUD + delete_weapon"
```

---

### Task 4: state_machine.py — phase 축소 + advance_visitor

**Files:**
- Modify: `backend/app/state_machine.py`
- Test: `backend/tests/test_state_machine.py`

- [ ] **Step 1: 실패하는 테스트 작성 (`test_state_machine.py`)**

기존 테스트 전부 삭제 후 새로 작성:

```python
import pytest
from app import state_machine as sm


def test_phases_simplified():
    assert sm.PHASES == ["forge_open", "visitor", "day_summary"]


def test_advance_phase_normal():
    assert sm.next_phase("forge_open") == "visitor"
    assert sm.next_phase("visitor") == "day_summary"


def test_advance_to_next_day_increments():
    player = {"current_day": 1, "current_phase": "day_summary",
              "current_visitor_index": 5, "day_schedule": [{"kind": "merchant"}]}
    sm.advance_to_next_day(player)
    assert player["current_day"] == 2
    assert player["current_phase"] == "forge_open"
    assert player["current_visitor_index"] == 0
    assert player["day_schedule"] == []


def test_advance_to_next_day_game_over_at_max():
    player = {"current_day": sm.MAX_DAY, "current_phase": "day_summary",
              "current_visitor_index": 0, "day_schedule": []}
    sm.advance_to_next_day(player)
    assert player["current_phase"] == "game_over"


def test_advance_visitor_increments_index():
    player = {"current_phase": "visitor", "current_visitor_index": 0,
              "day_schedule": [{"kind": "new_hero"}, {"kind": "merchant"}, {"kind": "new_hero"}]}
    sm.advance_visitor(player)
    assert player["current_visitor_index"] == 1
    assert player["current_phase"] == "visitor"


def test_advance_visitor_last_slot_transitions_to_summary():
    player = {"current_phase": "visitor", "current_visitor_index": 1,
              "day_schedule": [{"kind": "merchant"}, {"kind": "new_hero"}]}
    sm.advance_visitor(player)
    assert player["current_phase"] == "day_summary"


def test_advance_visitor_outside_visitor_phase_raises():
    player = {"current_phase": "forge_open", "current_visitor_index": 0,
              "day_schedule": []}
    with pytest.raises(sm.PhaseError):
        sm.advance_visitor(player)


def test_assert_phase_unchanged_api():
    sm.assert_phase("forge_open", "forge_open")
    with pytest.raises(sm.PhaseError):
        sm.assert_phase("forge_open", "visitor")
```

- [ ] **Step 2: Run tests — should fail**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_state_machine.py -v`
Expected: FAIL (PHASES still has 9 items, no advance_visitor).

- [ ] **Step 3: state_machine.py 재작성**

```python
class PhaseError(Exception):
    pass


PHASES = ["forge_open", "visitor", "day_summary"]
INITIAL_PHASE = PHASES[0]
MAX_DAY = 100


def next_phase(current: str) -> str:
    if current == "day_summary":
        return "next_day"
    if current == "game_over":
        raise PhaseError("no phase after game_over")
    if current not in PHASES:
        raise PhaseError(f"unknown phase: {current}")
    idx = PHASES.index(current)
    return PHASES[idx + 1]


def assert_phase(current: str, expected: str) -> None:
    if current != expected:
        raise PhaseError(f"expected phase {expected}, got {current}")


def assert_phase_in(current: str, expected: list[str]) -> None:
    if current not in expected:
        raise PhaseError(f"expected one of {expected}, got {current}")


def advance_visitor(player: dict) -> None:
    """visitor 슬롯 인덱스 ++. 마지막 슬롯이면 day_summary로 전이."""
    if player["current_phase"] != "visitor":
        raise PhaseError(f"advance_visitor requires phase=visitor, got {player['current_phase']}")
    schedule = player.get("day_schedule", [])
    new_idx = player["current_visitor_index"] + 1
    if new_idx >= len(schedule):
        player["current_phase"] = "day_summary"
    else:
        player["current_visitor_index"] = new_idx


def advance_to_next_day(player: dict) -> None:
    """player dict in-place 갱신. MAX_DAY 도달 시 game_over."""
    if player["current_day"] >= MAX_DAY:
        player["current_phase"] = "game_over"
    else:
        player["current_day"] += 1
        player["current_phase"] = "forge_open"
        player["current_visitor_index"] = 0
        player["day_schedule"] = []
```

- [ ] **Step 4: Run tests — should pass**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_state_machine.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/state_machine.py backend/tests/test_state_machine.py
git commit -m "feat(state-machine): simplify to 3 phases + add advance_visitor"
```

---

### Task 5: scheduler.py — 평판 기반 슬롯 수 + 시드 헬퍼

**Files:**
- Create: `backend/app/scheduler.py`
- Create: `backend/tests/test_scheduler.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_scheduler.py`:

```python
import pytest
from app import scheduler


@pytest.mark.parametrize("rep,expected_min,expected_max", [
    (0, 3, 3), (5, 3, 3), (10, 3, 3),
    (11, 3, 5), (15, 3, 5), (20, 3, 5),
    (21, 5, 7), (30, 5, 7), (40, 5, 7),
    (41, 8, 10), (60, 8, 10),
    (61, 10, 10), (200, 10, 10),
])
def test_hero_slot_count_range(rep, expected_min, expected_max):
    counts = {scheduler.hero_slot_count(rep, seed=s) for s in range(50)}
    assert min(counts) >= expected_min
    assert max(counts) <= expected_max


def test_hero_slot_count_deterministic_same_seed():
    assert scheduler.hero_slot_count(15, seed=42) == scheduler.hero_slot_count(15, seed=42)


def test_schedule_seed_changes_per_day():
    assert scheduler.schedule_seed(player_id=1, day=1) != scheduler.schedule_seed(player_id=1, day=2)


def test_schedule_seed_changes_per_player():
    assert scheduler.schedule_seed(player_id=1, day=1) != scheduler.schedule_seed(player_id=2, day=1)


def test_resolve_day_survive_range():
    days = {scheduler.resolve_day_for("survive", depart_day=10, seed=s) for s in range(100)}
    assert days <= {12, 13}
    assert days == {12, 13}  # 충분히 시드 굴리면 두 값 모두 나옴


def test_resolve_day_injure_range():
    days = {scheduler.resolve_day_for("injure", depart_day=10, seed=s) for s in range(200)}
    assert days <= {15, 16, 17}
    assert days == {15, 16, 17}


def test_resolve_day_die_range():
    days = {scheduler.resolve_day_for("die", depart_day=10, seed=s) for s in range(100)}
    assert days <= {11, 12}
    assert days == {11, 12}


def test_build_schedule_inserts_merchant_once():
    pending = []
    sched = scheduler.build_schedule(player_id=1, day=5, reputation=0, pending_revisits=pending)
    merchant_count = sum(1 for s in sched if s["kind"] == "merchant")
    assert merchant_count == 1


def test_build_schedule_total_length():
    # 평판 0 → 용사 3 + 상인 1 = 4
    sched = scheduler.build_schedule(player_id=1, day=5, reputation=0, pending_revisits=[])
    assert len(sched) == 4


def test_build_schedule_revisits_take_priority():
    # 평판 0 (3 슬롯) + 재방문 2 → 신규 1
    revisits = [
        {"id": 100, "hero_id": 11, "kind": "revisit_survive"},
        {"id": 101, "hero_id": 12, "kind": "revisit_injure"},
    ]
    sched = scheduler.build_schedule(player_id=1, day=5, reputation=0, pending_revisits=revisits)
    returning = [s for s in sched if s["kind"] == "returning_hero"]
    new_heroes = [s for s in sched if s["kind"] == "new_hero"]
    assert len(returning) == 2
    assert len(new_heroes) == 1
    assert sum(1 for s in sched if s["kind"] == "merchant") == 1


def test_build_schedule_overflow_returns_postponed_ids():
    # 평판 0 (3 슬롯) + 재방문 5 → 신규 0, 2개는 postponed
    revisits = [
        {"id": 200 + i, "hero_id": 20 + i, "kind": "revisit_survive"} for i in range(5)
    ]
    sched = scheduler.build_schedule(player_id=1, day=5, reputation=0, pending_revisits=revisits)
    returning = [s for s in sched if s["kind"] == "returning_hero"]
    assert len(returning) == 3
    postponed = scheduler.postponed_outcome_ids(revisits, taken=returning)
    assert len(postponed) == 2
    assert set(postponed) == {204, 203}  # 마지막 2개 밀림 (안정 정렬)


def test_build_schedule_same_seed_same_output():
    sched_a = scheduler.build_schedule(player_id=1, day=5, reputation=30, pending_revisits=[])
    sched_b = scheduler.build_schedule(player_id=1, day=5, reputation=30, pending_revisits=[])
    assert sched_a == sched_b
```

- [ ] **Step 2: Run tests — should fail**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_scheduler.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: scheduler.py 구현**

```python
"""하루 방문자 스케줄 생성. 결정성 시드로 재현 가능."""
from __future__ import annotations
import random
from typing import Any

REP_TIERS = [
    (10, (3, 3)),
    (20, (3, 5)),
    (40, (5, 7)),
    (60, (8, 10)),
    (10**9, (10, 10)),
]


def schedule_seed(player_id: int, day: int) -> int:
    return (player_id * 1_000_003 + day * 31 + 11) & 0xFFFFFFFF


def hero_slot_count(reputation: int, seed: int) -> int:
    for upper, (lo, hi) in REP_TIERS:
        if reputation <= upper:
            if lo == hi:
                return lo
            return random.Random(seed).randint(lo, hi)
    return 10


def resolve_day_for(outcome: str, depart_day: int, seed: int) -> int:
    """outcome: 'survive'|'injure'|'die'. seed 별로 범위 내 결정성 선택."""
    rng = random.Random(seed)
    if outcome == "survive":
        return depart_day + rng.randint(2, 3)
    if outcome == "injure":
        return depart_day + rng.randint(5, 7)
    if outcome == "die":
        return depart_day + rng.randint(1, 2)
    raise ValueError(f"unknown outcome: {outcome}")


def build_schedule(
    player_id: int,
    day: int,
    reputation: int,
    pending_revisits: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """그 날 방문자 큐를 생성한다.

    pending_revisits: [{id, hero_id, kind}] — 오늘 resolve될 revisit_* 항목들.
                      입력 순서가 안정성 기준 (id 오름차순으로 미리 정렬해 넘길 것).
    """
    seed = schedule_seed(player_id, day)
    rng = random.Random(seed)

    n_hero_slots = hero_slot_count(reputation, seed=seed ^ 0x5A5A5A5A)

    # 재방문 먼저 N개까지 채움
    taken_revisits = pending_revisits[:n_hero_slots]
    n_new = n_hero_slots - len(taken_revisits)

    visitor_entries: list[dict[str, Any]] = []
    for r in taken_revisits:
        visitor_entries.append({
            "kind": "returning_hero",
            "hero_id": r["hero_id"],
            "outcome_id": r["id"],
        })

    # 신규 용사 hero_id는 hero_registry에서 day 진입 시점에 채워야 하므로,
    # 여기선 placeholder를 둔다. 실제 채움은 forge_open 처리(Task 8)에서.
    for i in range(n_new):
        visitor_entries.append({"kind": "new_hero", "hero_id": None, "_new_slot": i})

    # 상인 1명 — 위치는 시드로 [0, N] 범위 결정 후 insert
    merchant_pos = rng.randrange(len(visitor_entries) + 1)
    visitor_entries.insert(merchant_pos, {"kind": "merchant"})

    return visitor_entries


def postponed_outcome_ids(
    pending_revisits: list[dict[str, Any]],
    taken: list[dict[str, Any]],
) -> list[int]:
    """슬롯에 못 들어간 outcome_id 목록 (resolve_day += 1 대상)."""
    taken_ids = {t["outcome_id"] for t in taken if t.get("kind") == "returning_hero"}
    return [r["id"] for r in pending_revisits if r["id"] not in taken_ids]
```

- [ ] **Step 4: Run tests — should pass**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_scheduler.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/scheduler.py backend/tests/test_scheduler.py
git commit -m "feat(scheduler): reputation-based slot count + deterministic schedule build"
```

---

### Task 6: combat.decide_outcomes 확장 — hero_opinion 반환

**Files:**
- Modify: `backend/app/combat.py:184` (decide_outcomes 시그니처)
- Test: `backend/tests/test_combat.py` (관련 테스트만)

- [ ] **Step 1: 현재 시그니처 확인**

Run: `sed -n '180,225p' backend/app/combat.py`

`decide_outcomes(hero, weapon, demon) -> dict` 의 반환 dict에 추가해야 할 키: `hero_opinion ∈ {"want_better_weapon", "weapon_broke", "none"}`.

- [ ] **Step 2: 실패하는 테스트 추가**

`backend/tests/test_combat.py` 맨 아래에 추가:

```python
def test_decide_outcomes_returns_hero_opinion():
    from app import combat
    hero = {"id": 1, "name": "테스트", "str": 5, "mag": 5, "level": 1}
    weapon = {"id": 1, "name": "검", "attack": 10, "durability": 5,
              "attribute": "화", "weapon_type": "검"}
    demon = {"id": "imp", "name": "임프", "hp": 5, "attack": 1, "attribute": "수"}
    result = combat.decide_outcomes(hero, weapon, demon)
    assert "hero_opinion" in result
    assert result["hero_opinion"] in {"want_better_weapon", "weapon_broke", "none"}


def test_decide_outcomes_weapon_broke_opinion_when_destroyed():
    from app import combat
    hero = {"id": 1, "name": "테스트", "str": 5, "mag": 5, "level": 1}
    weapon = {"id": 1, "name": "검", "attack": 10, "durability": 0,
              "attribute": "화", "weapon_type": "검"}
    demon = {"id": "imp", "name": "임프", "hp": 5, "attack": 1, "attribute": "수"}
    result = combat.decide_outcomes(hero, weapon, demon)
    if result.get("weapon") == "destroyed":
        assert result["hero_opinion"] == "weapon_broke"
```

- [ ] **Step 3: Run tests — should fail**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_combat.py::test_decide_outcomes_returns_hero_opinion -v`
Expected: FAIL.

- [ ] **Step 4: decide_outcomes 수정**

`backend/app/combat.py`의 `decide_outcomes` 함수를 열고, 반환 dict 마지막에 다음 로직을 추가한다 (정확한 함수 본문은 파일을 읽고 결정; 핵심은 반환 dict에 `hero_opinion` 키를 추가):

```python
# decide_outcomes 마지막 (return 직전):
if outcomes.get("weapon") == "destroyed":
    outcomes["hero_opinion"] = "weapon_broke"
elif outcomes.get("hero") == "survived" and outcomes.get("demon") != "killed":
    outcomes["hero_opinion"] = "want_better_weapon"
else:
    outcomes["hero_opinion"] = "none"
```

- [ ] **Step 5: Run tests — should pass**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_combat.py::test_decide_outcomes_returns_hero_opinion tests/test_combat.py::test_decide_outcomes_weapon_broke_opinion_when_destroyed -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/combat.py backend/tests/test_combat.py
git commit -m "feat(combat): decide_outcomes returns hero_opinion"
```

---

### Task 7: pending_outcomes.py — 출정 시점 처리 모듈

**Files:**
- Create: `backend/app/pending_outcomes.py`
- Create: `backend/tests/test_pending_outcomes.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_pending_outcomes.py`:

```python
from unittest.mock import patch
from app import pending_outcomes as po


def _hero(**kw):
    return {"id": 1, "name": "H", "str": 5, "mag": 5, "level": 1, **kw}


def _weapon(**kw):
    return {"id": 10, "name": "검", "attack": 10, "durability": 5,
            "attribute": "화", "weapon_type": "검", **kw}


def _demon(**kw):
    return {"id": "imp", "name": "임프", "hp": 5, "attack": 1, "attribute": "수", **kw}


@patch("app.pending_outcomes.repo")
def test_dispatch_writes_pending_and_deletes_weapon(mock_repo, fake_repo):
    # fake_repo는 conftest fixture; mock_repo 모듈도 fake_repo로 라우팅
    mock_repo.insert_pending_outcome.side_effect = fake_repo.insert_pending_outcome
    mock_repo.delete_weapon.side_effect = fake_repo.delete_weapon

    fake_repo.weapons.append(_weapon())
    player = {"id": 1, "current_day": 10}
    hero = _hero()
    weapon = _weapon()
    demon = _demon()
    result = po.dispatch_hero(player, hero, weapon, demon)
    assert "outcome_id" in result
    assert "outcome" in result
    assert result["outcome"]["hero"] in {"survived", "injured", "died"}
    # weapon 삭제됨
    assert all(w["id"] != 10 for w in fake_repo.weapons)
    # pending_outcomes 한 건 박힘
    assert len(fake_repo.pending_outcomes) == 1
    pending = fake_repo.pending_outcomes[0]
    assert pending["depart_day"] == 10
    assert pending["resolve_day"] >= 11
    assert pending["kind"] in {"revisit_survive", "revisit_injure", "death_mail"}
    assert pending["weapon_snapshot"]["id"] == 10


@patch("app.pending_outcomes.repo")
def test_dispatch_deterministic(mock_repo, fake_repo):
    mock_repo.insert_pending_outcome.side_effect = fake_repo.insert_pending_outcome
    mock_repo.delete_weapon.side_effect = fake_repo.delete_weapon

    player = {"id": 1, "current_day": 5}
    a = po.dispatch_hero(player, _hero(), _weapon(), _demon())
    fake_repo.pending_outcomes.clear()
    fake_repo.weapons.append(_weapon())
    b = po.dispatch_hero(player, _hero(), _weapon(), _demon())
    assert a["outcome"] == b["outcome"]
    assert fake_repo.pending_outcomes[0]["resolve_day"] == a["resolve_day"] == b["resolve_day"]
```

`fake_repo` fixture가 conftest에 없으면 추가해야 한다. conftest.py 끝에:

```python
import pytest

@pytest.fixture
def fake_repo():
    return FakeRepo()
```

- [ ] **Step 2: Run tests — should fail (module missing)**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_pending_outcomes.py -v`
Expected: FAIL.

- [ ] **Step 3: 구현**

```python
"""용사 출정 시점에 outcome을 결정하고 pending_outcomes에 박는다."""
from __future__ import annotations
from typing import Any

from . import combat, repo, scheduler


def _outcome_seed(player_id: int, depart_day: int, hero_id: int) -> int:
    return (player_id * 1_000_003 + depart_day * 31 + (hero_id * 7) + 13) & 0xFFFFFFFF


def _kind_for(hero_status: str) -> str:
    if hero_status == "died":
        return "death_mail"
    if hero_status == "injured":
        return "revisit_injure"
    return "revisit_survive"


def _outcome_label(hero_status: str) -> str:
    if hero_status == "died":
        return "die"
    if hero_status == "injured":
        return "injure"
    return "survive"


def dispatch_hero(
    player: dict[str, Any],
    hero: dict[str, Any],
    weapon: dict[str, Any] | None,
    demon: dict[str, Any],
) -> dict[str, Any]:
    """협상 수락 직후 호출. outcome 결정 → pending_outcomes insert → weapon 삭제."""
    depart_day = player["current_day"]
    seed = _outcome_seed(player["id"], depart_day, hero["id"])

    outcome = combat.decide_outcomes(hero, weapon, demon)
    label = _outcome_label(outcome["hero"])
    resolve_day = scheduler.resolve_day_for(label, depart_day, seed=seed + 7)
    kind = _kind_for(outcome["hero"])

    weapon_snapshot = dict(weapon) if weapon else {}

    saved = repo.insert_pending_outcome({
        "player_id": player["id"],
        "hero_id": hero["id"],
        "depart_day": depart_day,
        "resolve_day": resolve_day,
        "kind": kind,
        "outcome_json": outcome,
        "weapon_snapshot": weapon_snapshot,
    })

    if weapon:
        repo.delete_weapon(weapon["id"])

    return {
        "outcome_id": saved["id"],
        "outcome": outcome,
        "resolve_day": resolve_day,
        "kind": kind,
    }
```

- [ ] **Step 4: Run tests — should pass**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_pending_outcomes.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/pending_outcomes.py backend/tests/test_pending_outcomes.py backend/tests/conftest.py
git commit -m "feat(pending-outcomes): dispatch_hero writes pending + deletes weapon"
```

---

### Task 8: forge_open 진입 처리 — 스케줄 생성 + 신규 용사 채움 + postpone

**Files:**
- Create: `backend/app/day_open.py` (forge_open 진입 시 호출되는 헬퍼)
- Test: `backend/tests/test_day_open.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_day_open.py`:

```python
from unittest.mock import patch
from app import day_open


@patch("app.day_open.hero_registry")
@patch("app.day_open.repo")
def test_prepare_day_builds_schedule_with_new_heroes(mock_repo, mock_hr, fake_repo):
    mock_repo.list_pending_to_resolve.side_effect = fake_repo.list_pending_to_resolve
    mock_repo.update_pending_resolve_day.side_effect = fake_repo.update_pending_resolve_day
    mock_repo.update_player.side_effect = lambda pid, **f: fake_repo.update_player(pid, **f)

    player = {"id": 1, "current_day": 3, "reputation": 0, "current_phase": "forge_open"}
    fake_repo.players[1] = player
    mock_hr.heroes_for_today.return_value = [
        {"id": 100, "name": "A"}, {"id": 101, "name": "B"}, {"id": 102, "name": "C"},
    ]
    result = day_open.prepare_day(player)
    assert len(result["schedule"]) == 4  # 3 hero + 1 merchant
    hero_ids = [s["hero_id"] for s in result["schedule"] if s["kind"] == "new_hero"]
    assert set(hero_ids) == {100, 101, 102}
    assert result["death_mails"] == []


@patch("app.day_open.hero_registry")
@patch("app.day_open.repo")
def test_prepare_day_extracts_death_mails(mock_repo, mock_hr, fake_repo):
    fake_repo.pending_outcomes.append({
        "id": 5, "player_id": 1, "hero_id": 50, "depart_day": 1, "resolve_day": 3,
        "kind": "death_mail", "outcome_json": {"hero": "died"},
        "weapon_snapshot": {"name": "검"}, "consumed": False,
    })
    mock_repo.list_pending_to_resolve.side_effect = fake_repo.list_pending_to_resolve
    mock_repo.update_pending_resolve_day.side_effect = fake_repo.update_pending_resolve_day
    mock_repo.update_player.side_effect = lambda pid, **f: fake_repo.update_player(pid, **f)

    player = {"id": 1, "current_day": 3, "reputation": 0, "current_phase": "forge_open"}
    fake_repo.players[1] = player
    mock_hr.heroes_for_today.return_value = [{"id": 100, "name": "A"}, {"id": 101, "name": "B"}, {"id": 102, "name": "C"}]
    result = day_open.prepare_day(player)
    assert len(result["death_mails"]) == 1
    assert result["death_mails"][0]["id"] == 5


@patch("app.day_open.hero_registry")
@patch("app.day_open.repo")
def test_prepare_day_postpones_overflow_revisits(mock_repo, mock_hr, fake_repo):
    # 평판 0 → 3 슬롯, 재방문 5개 → 2개는 resolve_day += 1
    for i in range(5):
        fake_repo.pending_outcomes.append({
            "id": 200 + i, "player_id": 1, "hero_id": 20 + i, "depart_day": 1,
            "resolve_day": 3, "kind": "revisit_survive",
            "outcome_json": {"hero": "survived"}, "weapon_snapshot": {}, "consumed": False,
        })
    mock_repo.list_pending_to_resolve.side_effect = fake_repo.list_pending_to_resolve
    mock_repo.update_pending_resolve_day.side_effect = fake_repo.update_pending_resolve_day
    mock_repo.update_player.side_effect = lambda pid, **f: fake_repo.update_player(pid, **f)

    player = {"id": 1, "current_day": 3, "reputation": 0, "current_phase": "forge_open"}
    fake_repo.players[1] = player
    mock_hr.heroes_for_today.return_value = []
    day_open.prepare_day(player)
    postponed = [p for p in fake_repo.pending_outcomes if p["resolve_day"] == 4]
    assert len(postponed) == 2


@patch("app.day_open.hero_registry")
@patch("app.day_open.repo")
def test_prepare_day_writes_schedule_to_player(mock_repo, mock_hr, fake_repo):
    mock_repo.list_pending_to_resolve.side_effect = fake_repo.list_pending_to_resolve
    mock_repo.update_pending_resolve_day.side_effect = fake_repo.update_pending_resolve_day
    mock_repo.update_player.side_effect = lambda pid, **f: fake_repo.update_player(pid, **f)

    player = {"id": 1, "current_day": 3, "reputation": 0, "current_phase": "forge_open"}
    fake_repo.players[1] = player
    mock_hr.heroes_for_today.return_value = [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}, {"id": 3, "name": "C"}]
    day_open.prepare_day(player)
    saved = fake_repo.players[1]
    assert "day_schedule" in saved
    assert saved["current_visitor_index"] == 0
```

FakeRepo의 `update_player`도 추가해야 한다 (conftest):

```python
def update_player(self, player_id: int, **fields):
    self.players[player_id].update(fields)
```

- [ ] **Step 2: Run tests — should fail**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_day_open.py -v`
Expected: FAIL.

- [ ] **Step 3: 구현**

```python
"""forge_open 진입 직후 호출되어 그 날 스케줄과 우편을 결정한다."""
from __future__ import annotations
from typing import Any

from . import hero_registry, repo, scheduler


def prepare_day(player: dict[str, Any]) -> dict[str, Any]:
    """player 행을 갱신: day_schedule, current_visitor_index 세팅.
    return: {schedule, death_mails}
    """
    day = player["current_day"]
    player_id = player["id"]

    pending = repo.list_pending_to_resolve(player_id, day)
    death_mails = [p for p in pending if p["kind"] == "death_mail"]
    revisits = [p for p in pending if p["kind"].startswith("revisit_")]
    revisits.sort(key=lambda p: p["id"])  # 안정 순서

    revisit_entries = [
        {"id": r["id"], "hero_id": r["hero_id"], "kind": r["kind"]} for r in revisits
    ]

    # 슬롯 수 계산용 placeholder 빌드 (신규 hero_id는 곧 채움)
    schedule = scheduler.build_schedule(
        player_id=player_id,
        day=day,
        reputation=player.get("reputation", 0),
        pending_revisits=revisit_entries,
    )

    # 신규 용사 채움
    n_new = sum(1 for s in schedule if s["kind"] == "new_hero")
    if n_new > 0:
        heroes = hero_registry.heroes_for_today(player_id, day)[:n_new]
        idx_iter = iter(heroes)
        for s in schedule:
            if s["kind"] == "new_hero":
                hero = next(idx_iter)
                s["hero_id"] = hero["id"]
                s.pop("_new_slot", None)

    # 슬롯 초과 revisit은 resolve_day += 1
    taken_outcome_ids = {s["outcome_id"] for s in schedule if s["kind"] == "returning_hero"}
    for r in revisits:
        if r["id"] not in taken_outcome_ids:
            repo.update_pending_resolve_day(r["id"], day + 1)

    repo.update_player(
        player_id,
        day_schedule=schedule,
        current_visitor_index=0,
    )

    return {"schedule": schedule, "death_mails": death_mails}
```

- [ ] **Step 4: Run tests — should pass**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_day_open.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/day_open.py backend/tests/test_day_open.py backend/tests/conftest.py
git commit -m "feat(day-open): prepare schedule + extract death mails on forge_open"
```

---

### Task 9: API /state 응답에 current_visitor + death_mails 노출

**Files:**
- Modify: `backend/app/api/state.py`
- Modify: `backend/app/api/day.py` (forge_open 진입 시 prepare_day 호출)
- Test: `backend/tests/test_visitor_endpoints.py` (신규)

- [ ] **Step 1: state.py 읽고 응답 구조 확인**

Run: `cat backend/app/api/state.py`

- [ ] **Step 2: state.py 수정 — 응답에 추가 필드**

GET `/state` 핸들러의 응답 dict에 다음을 추가:

```python
schedule = player.get("day_schedule", [])
idx = player.get("current_visitor_index", 0)
current_visitor = schedule[idx] if (player["current_phase"] == "visitor" and idx < len(schedule)) else None

death_mails = []
if player["current_phase"] == "forge_open":
    pending = repo.list_pending_to_resolve(player["id"], player["current_day"])
    death_mails = [
        {"id": p["id"], "hero_id": p["hero_id"], "weapon_snapshot": p["weapon_snapshot"],
         "outcome": p["outcome_json"]}
        for p in pending if p["kind"] == "death_mail" and not p["consumed"]
    ]

response["current_visitor"] = current_visitor
response["death_mails"] = death_mails
response["day_schedule"] = schedule
response["current_visitor_index"] = idx
```

- [ ] **Step 3: day.py — /day/forge/done 핸들러에서 forge_open → visitor 전이 시 prepare_day 호출 확인**

`/day/forge/done` (제작 완료, phase 전이) 핸들러를 찾아 다음 흐름이 되도록 수정:

```python
# forge_done 시점:
state_machine.assert_phase(player["current_phase"], "forge_open")
# 스케줄이 비어있다면 prepare_day 호출
if not player.get("day_schedule"):
    day_open.prepare_day(player)
    player = repo.load_player(player["id"])  # 갱신본 다시 로드
repo.update_player(player["id"], current_phase="visitor")
```

또한 `/day/next` 의 advance_to_next_day 직후에는 day_schedule이 비워졌으므로, 다음 forge_open 시 prepare_day가 호출되어야 한다 (forge_done 시점에서 처리됨).

- [ ] **Step 4: 간단한 통합 테스트**

`backend/tests/test_visitor_endpoints.py`:

```python
from fastapi.testclient import TestClient
from app.main import app


def test_state_returns_current_visitor_during_visitor_phase(monkeypatch_fake_repo):
    """fake_repo fixture로 백엔드 전체를 띄우고, forge_done 후 /state 호출 시 current_visitor 노출."""
    client = TestClient(app)
    headers = {"X-Player-Nickname": "tester"}

    # 초기 상태
    r = client.get("/state", headers=headers)
    assert r.status_code == 200

    # forge 완료
    r = client.post("/day/forge/done", headers=headers)
    assert r.status_code in (200, 204)

    r = client.get("/state", headers=headers)
    body = r.json()
    assert body["current_phase"] == "visitor"
    assert body["current_visitor"] is not None
    assert body["current_visitor"]["kind"] in {"new_hero", "merchant", "returning_hero"}
```

`monkeypatch_fake_repo` fixture는 conftest에 추가 — `app.repo` 모듈의 모든 함수를 FakeRepo 메서드로 patch하는 fixture. (이미 다른 통합 테스트에 있다면 재사용.)

Run: `grep -rn "monkeypatch_fake_repo\|patch_repo" backend/tests/ | head`

이미 비슷한 패턴이 있으면 그걸 사용하고, 없으면 conftest에 추가:

```python
@pytest.fixture
def monkeypatch_fake_repo(monkeypatch):
    fake = FakeRepo()
    from app import repo as real_repo
    for name in dir(fake):
        if name.startswith("_"):
            continue
        attr = getattr(fake, name)
        if callable(attr):
            monkeypatch.setattr(real_repo, name, attr, raising=False)
    return fake
```

- [ ] **Step 5: Run tests**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_visitor_endpoints.py -v`
Expected: PASS (또는 endpoint 미존재로 FAIL → Task 10/11에서 수정).

만약 forge_done 엔드포인트가 다른 경로명이면 (예: `/forge/done`) 그대로 맞춰 사용.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/state.py backend/app/api/day.py backend/tests/test_visitor_endpoints.py backend/tests/conftest.py
git commit -m "feat(api): /state exposes current_visitor + death_mails; forge_done triggers prepare_day"
```

---

### Task 10: 통합 visitor 엔드포인트 — /visitor/current/*

**Files:**
- Create: `backend/app/api/visitor.py`
- Modify: `backend/app/api/__init__.py`, `backend/app/main.py`

- [ ] **Step 1: visitor.py 구현**

```python
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException

from .. import repo, state_machine, pending_outcomes, bosses
from ..auth import current_player

router = APIRouter(prefix="/visitor", tags=["visitor"])


def _current_slot(player: dict) -> dict:
    state_machine.assert_phase(player["current_phase"], "visitor")
    schedule = player.get("day_schedule") or []
    idx = player["current_visitor_index"]
    if idx >= len(schedule):
        raise HTTPException(409, "no current visitor (schedule exhausted)")
    return schedule[idx]


def _advance_and_save(player: dict) -> None:
    state_machine.advance_visitor(player)
    repo.update_player(
        player["id"],
        current_phase=player["current_phase"],
        current_visitor_index=player.get("current_visitor_index", 0),
    )


@router.post("/current/return")
def finish_returning_hero(player=Depends(current_player)):
    slot = _current_slot(player)
    if slot["kind"] != "returning_hero":
        raise HTTPException(409, "current slot is not returning_hero")
    repo.mark_pending_consumed(slot["outcome_id"])
    _advance_and_save(player)
    return {"ok": True}


@router.post("/current/skip")
def skip_visitor(player=Depends(current_player)):
    """협상 거절/상인 패스 등 일반 advance."""
    _current_slot(player)
    _advance_and_save(player)
    return {"ok": True}
```

협상 수락(`accept`)은 기존 `negotiate` 라우터 안에서 처리되므로, 그쪽에서 dispatch_hero + advance 호출.

- [ ] **Step 2: api/__init__.py 와 main.py에서 라우터 등록**

`backend/app/main.py`를 열고 (또는 `api/__init__.py`):

```python
from .api import visitor as visitor_api
app.include_router(visitor_api.router)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/visitor.py backend/app/main.py backend/app/api/__init__.py
git commit -m "feat(api): /visitor/current/{return,skip} unified endpoints"
```

---

### Task 11: negotiate accept → 비동기 dispatch로 교체

**Files:**
- Modify: `backend/app/api/negotiate.py` (또는 협상 라우터)
- Modify: `backend/app/api/battle.py` (제거 또는 deprecation)

- [ ] **Step 1: 현재 negotiate accept 흐름 확인**

Run: `cat backend/app/api/negotiate.py`

`accept` 분기에서 현재 `combat.run_battle` 등을 호출할 것이다.

- [ ] **Step 2: accept 분기 재작성**

협상 수락 시:

```python
# 기존: 거래 처리 → run_battle (즉시 전투)
# 변경: 거래 처리 → pending_outcomes.dispatch_hero → advance_visitor

# 골드 이동, weapon owner 변경 등 기존 거래 로직은 유지
...

# 새 로직
demon = bosses.demon_for_today(player["id"], player["current_day"])  # 기존 함수 시그니처에 맞춰
weapon = repo.get_weapon(weapon_id) if weapon_id else None
hero = repo.get_hero(hero_id)
dispatch = pending_outcomes.dispatch_hero(player, hero, weapon, demon)

# 엔딩 감지 (기존 run_battle 안에 있던 호출을 여기로)
endgame.detect_ending(player, latest_outcome=dispatch["outcome"])

# 슬롯 advance
state_machine.advance_visitor(player)
repo.update_player(player["id"],
                   current_phase=player["current_phase"],
                   current_visitor_index=player.get("current_visitor_index", 0))

return {"accepted": True, "outcome_id": dispatch["outcome_id"]}
```

- [ ] **Step 3: battle.py 제거**

```bash
git rm backend/app/api/battle.py
```

main.py 에서 battle 라우터 include 도 제거.

- [ ] **Step 4: 관련 테스트 정리**

`backend/tests/test_negotiation.py` 의 accept → battle 흐름 검증 테스트를 → "accept 시 pending_outcomes에 한 건 박힘 + weapon 삭제 + 슬롯 advance" 로 재작성.

`backend/tests/test_integration_day.py` 도 hero1_battle phase 가정을 visitor 인덱스로 교체.

- [ ] **Step 5: Run tests**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_negotiation.py tests/test_integration_day.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(negotiate): accept dispatches to pending_outcomes; remove sync battle endpoint"
```

---

### Task 12: 우편 ack 엔드포인트

**Files:**
- Create: `backend/app/api/mail.py`
- Create: `backend/tests/test_death_mail.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 실패 테스트**

```python
from fastapi.testclient import TestClient
from app.main import app


def test_death_mail_ack_marks_consumed(monkeypatch_fake_repo):
    fake = monkeypatch_fake_repo
    fake.pending_outcomes.append({
        "id": 99, "player_id": 1, "hero_id": 1, "depart_day": 1, "resolve_day": 1,
        "kind": "death_mail", "outcome_json": {"hero": "died"},
        "weapon_snapshot": {}, "consumed": False,
    })
    fake.players[1] = {"id": 1, "nickname": "tester", "current_day": 1,
                       "current_phase": "forge_open", "current_visitor_index": 0,
                       "day_schedule": [], "reputation": 0}
    client = TestClient(app)
    r = client.post("/mail/99/ack", headers={"X-Player-Nickname": "tester"})
    assert r.status_code == 200
    assert any(p["id"] == 99 and p["consumed"] for p in fake.pending_outcomes)
```

- [ ] **Step 2: 구현 (mail.py)**

```python
from fastapi import APIRouter, Depends, HTTPException
from .. import repo
from ..auth import current_player

router = APIRouter(prefix="/mail", tags=["mail"])


@router.post("/{outcome_id}/ack")
def ack(outcome_id: int, player=Depends(current_player)):
    p = repo.get_pending(outcome_id)
    if not p or p["player_id"] != player["id"]:
        raise HTTPException(404, "mail not found")
    if p["kind"] != "death_mail":
        raise HTTPException(400, "not a death mail")
    repo.mark_pending_consumed(outcome_id)
    return {"ok": True}
```

main.py에 라우터 등록.

- [ ] **Step 3: Run tests**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_death_mail.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/mail.py backend/tests/test_death_mail.py backend/app/main.py
git commit -m "feat(api): POST /mail/{id}/ack to consume death mail"
```

---

### Task 13: 재방문 LLM 회고 narration

**Files:**
- Modify: `backend/app/llm/prompts/` (재방문 회고 프롬프트 추가)
- Modify: `backend/app/api/state.py` (returning_hero 슬롯 응답에 회고 텍스트 포함)

- [ ] **Step 1: 회고 프롬프트 작성**

`backend/app/llm/prompts/returning_hero_recap.py` (또는 기존 prompts 구조에 맞춰):

```python
TEMPLATE = """\
당신은 {hero_name}({hero_job}) 입니다. {depart_day}일째에 대장장이에게서 {weapon_name}을(를) 받고 출정했고, 오늘({today})에 가게로 돌아왔습니다.
전투 결과: 잡은 몹 = {monsters_killed}, 무기 상태 = {weapon_state}, 당신의 상태 = {hero_state}.

3~5문장 짧은 회고로, 그동안의 사냥을 회상하며 결과를 자연스럽게 전달하세요. 결과를 바꾸지 말고, 위 사실에 충실하세요.
"""
```

- [ ] **Step 2: 회고 생성 함수**

`backend/app/returning_recap.py`:

```python
from typing import Any
from .llm import client as llm_client
from .llm.prompts.returning_hero_recap import TEMPLATE


def generate_recap(player: dict[str, Any], pending: dict[str, Any], hero: dict[str, Any]) -> str:
    outcome = pending["outcome_json"]
    weapon = pending["weapon_snapshot"]
    prompt = TEMPLATE.format(
        hero_name=hero.get("name", "?"),
        hero_job=hero.get("job", "?"),
        depart_day=pending["depart_day"],
        weapon_name=weapon.get("name", "무기"),
        today=player["current_day"],
        monsters_killed=outcome.get("monsters_killed", 0),
        weapon_state="파손" if outcome.get("weapon") == "destroyed" else "정상",
        hero_state=outcome.get("hero", "?"),
    )
    return llm_client.generate(prompt)
```

- [ ] **Step 3: state.py 에서 returning_hero 슬롯이면 recap 포함**

```python
# state response build 시
if current_visitor and current_visitor["kind"] == "returning_hero":
    pending = repo.get_pending(current_visitor["outcome_id"])
    hero = repo.get_hero(current_visitor["hero_id"])
    current_visitor["recap"] = returning_recap.generate_recap(player, pending, hero)
    current_visitor["outcome"] = pending["outcome_json"]
    current_visitor["weapon_snapshot"] = pending["weapon_snapshot"]
```

캐싱 고려: 매 /state 호출마다 LLM 호출하지 않도록, recap은 첫 노출 시 생성해 `pending_outcomes` row에 저장하는 것이 좋다.

`pending_outcomes` 테이블에 `recap TEXT` 컬럼이 없으니 마이그레이션 010을 추가하거나, `outcome_json` 안에 박는다. 본 계획에선 `outcome_json["recap"]`에 캐싱:

```python
if not pending["outcome_json"].get("recap"):
    recap = returning_recap.generate_recap(player, pending, hero)
    pending["outcome_json"]["recap"] = recap
    repo.update_pending_outcome(pending["id"], outcome_json=pending["outcome_json"])
```

`repo.update_pending_outcome` 함수도 추가 (Task 3 패턴):

```python
def update_pending_outcome(outcome_id: int, **fields):
    _client().table("pending_outcomes").update(fields).eq("id", outcome_id).execute()
```

FakeRepo에도 동일 메서드 추가.

- [ ] **Step 4: 간단한 테스트**

`backend/tests/test_returning_recap.py`:

```python
from unittest.mock import patch
from app import returning_recap


@patch("app.returning_recap.llm_client")
def test_generate_recap_uses_outcome(mock_llm):
    mock_llm.generate.return_value = "회고 텍스트"
    player = {"current_day": 10}
    pending = {"depart_day": 7, "outcome_json": {"hero": "survived", "monsters_killed": 3, "weapon": "normal"},
               "weapon_snapshot": {"name": "검"}}
    hero = {"name": "A", "job": "검사"}
    out = returning_recap.generate_recap(player, pending, hero)
    assert out == "회고 텍스트"
    args = mock_llm.generate.call_args[0][0]
    assert "monsters_killed=3" not in args  # 포맷된 값이라 raw 키는 없음
    assert "잡은 몹 = 3" in args
```

LLM_FIXTURE_DIR 환경에선 실제 API 호출이 fixture 파일에서 로드되므로, 픽스처 추가 가이드도 README에 있을 것 — 일단 모킹으로 처리.

- [ ] **Step 5: Run + Commit**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_returning_recap.py -v`
Expected: PASS.

```bash
git add -A
git commit -m "feat(llm): returning hero recap narration cached on outcome_json"
```

---

### Task 14: Frontend — 타입 + API 래퍼

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/api.ts`

- [ ] **Step 1: 타입 추가**

`frontend/src/types.ts` 끝에:

```typescript
export type VisitorKind = "new_hero" | "returning_hero" | "merchant";

export interface CurrentVisitor {
  kind: VisitorKind;
  hero_id?: number;
  outcome_id?: number;
  outcome?: BattleOutcome;
  weapon_snapshot?: WeaponSnapshot;
  recap?: string;
}

export interface DeathMail {
  id: number;
  hero_id: number;
  weapon_snapshot: WeaponSnapshot;
  outcome: BattleOutcome;
}

export interface BattleOutcome {
  hero: "survived" | "injured" | "died";
  weapon?: "normal" | "destroyed";
  monsters_killed?: number;
  hero_opinion?: "want_better_weapon" | "weapon_broke" | "none";
}

export interface WeaponSnapshot {
  id?: number;
  name?: string;
  attack?: number;
  attribute?: string;
  weapon_type?: string;
}

// State 인터페이스에 필드 추가
// (기존 State 타입을 찾아 다음 필드를 union으로 추가)
//   current_visitor: CurrentVisitor | null
//   death_mails: DeathMail[]
//   day_schedule: CurrentVisitor[]
//   current_visitor_index: number
```

- [ ] **Step 2: API 래퍼 추가**

`frontend/src/api.ts` 끝에:

```typescript
export const visitorReturn = () => post("/visitor/current/return");
export const visitorSkip = () => post("/visitor/current/skip");
export const mailAck = (id: number) => post(`/mail/${id}/ack`);
```

기존 `post` 헬퍼 형식에 맞춰서.

- [ ] **Step 3: 타입체크**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS (또는 State 타입 누락 컴파일 에러 → 수정).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types.ts frontend/src/api.ts
git commit -m "feat(frontend): types + api wrappers for visitor/mail"
```

---

### Task 15: Frontend DayRouter 단순화 + VisitorRouter

**Files:**
- Modify: `frontend/src/components/DayRouter.tsx`
- Create: `frontend/src/components/VisitorRouter.tsx`
- Create: `frontend/src/components/ReturningHeroPanel.tsx`
- Modify: `frontend/src/components/NegotiationChat.tsx`, `frontend/src/components/MerchantPanel.tsx`

- [ ] **Step 1: DayRouter 재작성**

```tsx
import { State } from "../types";
import ForgePanel from "./ForgePanel";
import VisitorRouter from "./VisitorRouter";
import DaySummary from "./DaySummary";
import GameOver from "./GameOver";

export default function DayRouter({ state, refresh }: { state: State; refresh: () => void }) {
  if (state.ending_kind) return <GameOver state={state} refresh={refresh} />;
  switch (state.current_phase) {
    case "forge_open":   return <ForgePanel state={state} refresh={refresh} />;
    case "visitor":      return <VisitorRouter state={state} refresh={refresh} />;
    case "day_summary":  return <DaySummary state={state} refresh={refresh} />;
    case "game_over":    return <GameOver state={state} refresh={refresh} />;
    default:             return <div>unknown phase: {state.current_phase}</div>;
  }
}
```

- [ ] **Step 2: VisitorRouter 작성**

```tsx
import { State } from "../types";
import NegotiationChat from "./NegotiationChat";
import MerchantPanel from "./MerchantPanel";
import ReturningHeroPanel from "./ReturningHeroPanel";

export default function VisitorRouter({ state, refresh }: { state: State; refresh: () => void }) {
  const v = state.current_visitor;
  if (!v) return <div>방문자 없음</div>;
  switch (v.kind) {
    case "new_hero":       return <NegotiationChat state={state} refresh={refresh} />;
    case "returning_hero": return <ReturningHeroPanel state={state} visitor={v} refresh={refresh} />;
    case "merchant":       return <MerchantPanel state={state} refresh={refresh} />;
  }
}
```

- [ ] **Step 3: ReturningHeroPanel 작성**

```tsx
import { State, CurrentVisitor } from "../types";
import { visitorReturn } from "../api";

export default function ReturningHeroPanel({
  state, visitor, refresh,
}: { state: State; visitor: CurrentVisitor; refresh: () => void }) {
  const outcome = visitor.outcome;
  const weaponName = visitor.weapon_snapshot?.name ?? "무기";
  return (
    <div className="returning-hero-panel">
      <h2>돌아온 용사</h2>
      <p className="recap">{visitor.recap ?? "..."}</p>
      <ul>
        <li>무기: {weaponName}</li>
        <li>상태: {outcome?.hero}</li>
        <li>잡은 몹: {outcome?.monsters_killed ?? 0}</li>
      </ul>
      <button onClick={async () => { await visitorReturn(); refresh(); }}>
        보내기
      </button>
    </div>
  );
}
```

- [ ] **Step 4: NegotiationChat / MerchantPanel — slot prop 제거**

기존에 `slot: 1 | 2 | 3` props를 받아 `/hero/${slot}/...` 으로 요청하던 부분을 `/visitor/current/...` 로 교체. State에서 `current_visitor.hero_id` 사용.

- [ ] **Step 5: 타입체크**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/
git commit -m "feat(frontend): DayRouter 3 phases + VisitorRouter + ReturningHeroPanel"
```

---

### Task 16: Frontend 사망 우편 모달

**Files:**
- Create: `frontend/src/components/DeathMailModal.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: DeathMailModal 작성**

```tsx
import { useState } from "react";
import { DeathMail } from "../types";
import { mailAck } from "../api";

export default function DeathMailModal({
  mails, onAcked,
}: { mails: DeathMail[]; onAcked: () => void }) {
  const [i, setI] = useState(0);
  if (mails.length === 0 || i >= mails.length) return null;
  const m = mails[i];
  return (
    <div className="modal-backdrop">
      <div className="modal death-mail">
        <h3>비보(悲報)</h3>
        <p>{m.weapon_snapshot.name ?? "무기"}을(를) 들고 떠난 용사가 돌아오지 못했습니다.</p>
        <p>잡은 몹: {m.outcome.monsters_killed ?? 0}</p>
        <button onClick={async () => {
          await mailAck(m.id);
          if (i + 1 >= mails.length) { onAcked(); } else { setI(i + 1); }
        }}>
          알겠다
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: App.tsx 마운트**

```tsx
{state.death_mails && state.death_mails.length > 0 && (
  <DeathMailModal mails={state.death_mails} onAcked={refresh} />
)}
```

- [ ] **Step 3: 수동 검증 (브라우저)**

Run: `cd backend && uvicorn app.main:app --reload --port 8000` (별도 터미널)
Run: `cd frontend && npm run dev`
브라우저 http://localhost:5173 에서 새 닉네임 로그인 → 며칠 진행 → 사망 우편 모달 확인.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/DeathMailModal.tsx frontend/src/App.tsx
git commit -m "feat(frontend): death mail modal"
```

---

### Task 17: 엔딩 감지 이동 검증

**Files:**
- Modify: `backend/tests/test_endgame.py`

- [ ] **Step 1: 기존 테스트 갱신**

`run_battle` 호출 후 `detect_ending`가 발동하던 테스트를 → `pending_outcomes.dispatch_hero` 호출 후 발동하도록 재작성. Task 11에서 negotiate accept 안에서 호출하도록 했으니, accept 통합 테스트로 검증.

```python
def test_surt_killed_ending_after_dispatch(monkeypatch_fake_repo):
    # 시나리오: 마지막 보스(surt)를 잡는 outcome이 결정되는 협상 accept 실행
    # → ending_kind == 'surt_killed'로 player 갱신
    ...
```

(상세 시나리오는 기존 test_endgame.py 케이스를 참고해 재구성.)

- [ ] **Step 2: Run**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_endgame.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_endgame.py
git commit -m "test: endgame detection now fires from dispatch_hero"
```

---

### Task 18: 전체 회귀 + 마이그레이션 적용 가이드

**Files:**
- Modify: `README.md` (선택)

- [ ] **Step 1: 전체 테스트**

Run: `cd backend && source .venv/bin/activate && python -m pytest -q`
Expected: 모두 PASS (혹은 deprecated된 hero1/2/3 phase 의존 테스트가 남아있다면 모두 visitor-index 모델로 갱신).

- [ ] **Step 2: 마이그레이션 실행**

사용자에게 안내:

```
Supabase Studio SQL Editor에서 backend/migrations/009_async_combat.sql 실행.
기존 진행 중 게임은 forge_open 상태로 정규화되며 다음 진입 시 day_schedule이 생성된다.
```

- [ ] **Step 3: 수동 플레이 검증**

브라우저에서 닉네임 새로 만들어 1차 시나리오 확인:
- forge_open → 제작 → visitor 진입 시 슬롯 큐 확인 (개발자도구 /state 응답)
- new_hero 협상 수락 → 슬롯 advance (즉시 결과 안 보임)
- 며칠 후 → returning_hero 슬롯 등장, 회고 LLM narration 표시
- 사망 케이스: 아침에 우편 모달

- [ ] **Step 4: 최종 commit (있다면)**

```bash
git add -A
git commit -m "chore: integration verification for async combat batch"
```

---

## 자가 점검

**Spec coverage:**
- 평판 → 슬롯 수 표 → Task 5
- 스케줄 큐 생성 → Task 5, 8
- pending_outcomes 테이블 → Task 1, 3
- 즉시 outcome 결정 + 지연 통보 → Task 7, 11
- 사망 우편 모달 → Task 12, 16
- 재방문 슬롯 회고 → Task 13, 15
- 무기 출정 시 DELETE → Task 7
- phase 3개 단순화 → Task 4, 15
- 엔딩 감지 위치 이동 → Task 11, 17
- /visitor/current/* 통합 → Task 10, 11
- 마이그레이션 + 기존 데이터 정규화 → Task 1
- 결정성 시드 유지 → Task 5, 7

**Out of scope (스펙대로 명시):**
- 전리품 거래 stub (Task 15에서 "보내기" 버튼만)
- chitchat, 인내심, 미션 NPC, 무기 칭호 — 후속 배치

# 미션 NPC 시스템 — 구현 계획 (3차 배치)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `mission_npc` 방문자 슬롯과 두 미션(세금관, 상인조합장)을 도입하고, 미션 실패 시 새 ending kind로 game_over를 트리거한다.

**Architecture:** 새 `missions` 테이블에 미션 인스턴스(kind/phase/due_day/status/payload)를 저장하고, `app/missions/` 패키지의 각 모듈이 `MissionModule` 인터페이스(plan/evaluate/slot_for/on_action)를 구현. `forge_open` 진입 시 `missions.scheduler.advance()`가 plan→evaluate→endgame을 처리하고 `today_slots()`가 그날 등장할 슬롯을 day_schedule 맨 앞에 prepend.

**Tech Stack:** Python 3.12 + FastAPI + Supabase + Pytest, React 18 + TypeScript + Vite.

**Spec:** `docs/superpowers/specs/2026-05-28-mission-npcs-design.md`

---

## File Structure

**Backend — create**
- `backend/migrations/012_missions.sql`
- `backend/app/missions/__init__.py` — 인터페이스 + 레지스트리
- `backend/app/missions/scheduler.py`
- `backend/app/missions/tax.py`
- `backend/app/missions/league_chief.py`
- `backend/app/api/mission.py` — `/visitor/current/mission_action`
- `backend/tests/test_mission_tax.py`
- `backend/tests/test_mission_league_chief.py`
- `backend/tests/test_mission_scheduler.py`
- `backend/tests/test_api_mission_action.py`

**Backend — modify**
- `backend/app/repo.py` — missions CRUD
- `backend/app/day_open.py` — missions.scheduler 통합
- `backend/app/api/state.py` — slot hydrate에 mission payload 펼침
- `backend/app/api/visitor.py` — mission_npc 슬롯에서 skip = on_action skip
- `backend/app/main.py` — mission 라우터 등록
- `backend/tests/fake_repo.py` — missions 메서드
- `backend/tests/test_day_open.py` — mission 슬롯 prepend 케이스 추가

**Frontend — create**
- `frontend/src/components/MissionPanel.tsx`
- `frontend/src/missions.ts` — 메시지/액션 매핑

**Frontend — modify**
- `frontend/src/types.ts` — VisitorKind에 `mission_npc`, CurrentVisitor 필드 확장
- `frontend/src/api.ts` — visitorMissionAction
- `frontend/src/components/VisitorRouter.tsx` — mission_npc 분기
- `frontend/src/endings.ts` — 새 두 종류

---

### Task 1: 마이그레이션 012

**Files:**
- Create: `backend/migrations/012_missions.sql`

- [ ] **Step 1: SQL 작성**

```sql
-- 012_missions.sql
CREATE TABLE IF NOT EXISTS missions (
  id         BIGSERIAL PRIMARY KEY,
  player_id  BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
  kind       TEXT NOT NULL,
  phase      TEXT NOT NULL,
  due_day    INT NOT NULL,
  status     TEXT NOT NULL DEFAULT 'pending',
  payload    JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  done_at    TIMESTAMPTZ,
  UNIQUE (player_id, kind, due_day, phase)
);
CREATE INDEX IF NOT EXISTS idx_missions_player_status
  ON missions(player_id, status, due_day);
```

- [ ] **Step 2: Supabase 적용 + 커밋** (MCP `apply_migration` 또는 Studio)

```bash
git add backend/migrations/012_missions.sql
git commit -m "migrate: 012 add missions table"
```

---

### Task 2: FakeRepo missions 메서드

**Files:**
- Modify: `backend/tests/fake_repo.py`

- [ ] **Step 1: 추가 (`__init__`에 컬렉션, 메서드 추가)**

`backend/tests/fake_repo.py`의 `__init__` 끝에:
```python
self.missions: list[dict[str, Any]] = []
self._mission_seq = 0
```

같은 클래스 안에 메서드 추가:
```python
def insert_mission(self, row: dict[str, Any]) -> dict[str, Any]:
    # UNIQUE (player_id, kind, due_day, phase) 모방
    key = (row["player_id"], row["kind"], row["due_day"], row["phase"])
    for m in self.missions:
        if (m["player_id"], m["kind"], m["due_day"], m["phase"]) == key:
            return m
    self._mission_seq += 1
    saved = {"id": self._mission_seq, "status": "pending", "payload": {},
             "done_at": None, **row}
    self.missions.append(saved)
    return saved

def update_mission(self, mission_id: int, **fields: Any) -> None:
    for m in self.missions:
        if m["id"] == mission_id:
            m.update(fields)
            return

def get_mission(self, mission_id: int) -> dict[str, Any] | None:
    return next((m for m in self.missions if m["id"] == mission_id), None)

def list_pending_missions(self, player_id: int) -> list[dict[str, Any]]:
    return [m for m in self.missions
            if m["player_id"] == player_id and m["status"] == "pending"]

def list_missions_today(self, player_id: int, day: int) -> list[dict[str, Any]]:
    return [m for m in self.missions
            if m["player_id"] == player_id and m["due_day"] == day
            and m["status"] == "pending"]
```

- [ ] **Step 2: Baseline 회귀**

Run: `cd backend && source .venv/bin/activate && python -m pytest -q`
Expected: 210 passed.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/fake_repo.py
git commit -m "test(fake_repo): add missions CRUD helpers"
```

---

### Task 3: repo.py missions CRUD

**Files:**
- Modify: `backend/app/repo.py`

- [ ] **Step 1: 파일 끝에 append**

```python
# --- 012: missions ---

def insert_mission(row: dict[str, Any]) -> dict[str, Any]:
    """UNIQUE (player_id, kind, due_day, phase)로 멱등 보장. 충돌 시 기존 행 반환."""
    c = _client()
    existing = c.table("missions").select("*") \
        .eq("player_id", row["player_id"]).eq("kind", row["kind"]) \
        .eq("due_day", row["due_day"]).eq("phase", row["phase"]) \
        .limit(1).execute().data
    if existing:
        return existing[0]
    return c.table("missions").insert(row).execute().data[0]


def update_mission(mission_id: int, **fields: Any) -> None:
    _client().table("missions").update(fields).eq("id", mission_id).execute()


def get_mission(mission_id: int) -> dict[str, Any] | None:
    rows = _client().table("missions").select("*").eq("id", mission_id).limit(1).execute().data
    return rows[0] if rows else None


def list_pending_missions(player_id: int) -> list[dict[str, Any]]:
    return _client().table("missions").select("*") \
        .eq("player_id", player_id).eq("status", "pending") \
        .order("due_day").execute().data


def list_missions_today(player_id: int, day: int) -> list[dict[str, Any]]:
    return _client().table("missions").select("*") \
        .eq("player_id", player_id).eq("due_day", day) \
        .eq("status", "pending").order("id").execute().data
```

- [ ] **Step 2: Import check + commit**

```bash
source .venv/bin/activate && python -c "from app import repo; print(repo.insert_mission, repo.list_pending_missions)"
git add backend/app/repo.py
git commit -m "repo: missions CRUD"
```

---

### Task 4: 미션 모듈 인터페이스 + 레지스트리

**Files:**
- Create: `backend/app/missions/__init__.py`

- [ ] **Step 1: 작성**

```python
"""미션 시스템 — 모듈 레지스트리.

각 미션 모듈은 다음 함수를 노출한다:
- plan(player, day) -> list[dict]            # 오늘 insert할 신규 미션 행
- evaluate(player, day, mission) -> tuple[str, str | None]
    # (new_status, ending_kind_or_None). new_status in {pending, done, failed, condition_met}
- slot_for(mission) -> dict                  # day_schedule entry
- on_action(player, mission, action) -> dict # 액션 처리. ValueError on invalid.
"""
from . import tax, league_chief

MODULES = {
    "tax": tax,
    "league_chief": league_chief,
}


def module_for(kind: str):
    if kind not in MODULES:
        raise ValueError(f"unknown mission kind: {kind}")
    return MODULES[kind]
```

- [ ] **Step 2: 빈 파일 stub** — tax, league_chief, scheduler를 다음 태스크에서 만들기 전에 import-가능한 stub.

`backend/app/missions/tax.py`:
```python
"""세금관 미션. (Task 5에서 구현)"""
def plan(player, day): return []
def evaluate(player, day, mission): return (mission["status"], None)
def slot_for(mission): return {"kind": "mission_npc", "mission_kind": "tax", "phase": mission["phase"]}
def on_action(player, mission, action): raise NotImplementedError
```

`backend/app/missions/league_chief.py`:
```python
"""상인조합장 미션. (Task 6에서 구현)"""
def plan(player, day): return []
def evaluate(player, day, mission): return (mission["status"], None)
def slot_for(mission): return {"kind": "mission_npc", "mission_kind": "league_chief", "phase": mission["phase"]}
def on_action(player, mission, action): raise NotImplementedError
```

- [ ] **Step 3: Import check + commit**

```bash
python -c "from app.missions import MODULES, module_for; print(list(MODULES))"
git add backend/app/missions/
git commit -m "feat(missions): registry + module stubs"
```

---

### Task 5: 세금관 미션 (`tax.py`)

**Files:**
- Modify: `backend/app/missions/tax.py`
- Create: `backend/tests/test_mission_tax.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# backend/tests/test_mission_tax.py
import pytest
from unittest.mock import patch
from app.missions import tax


def test_plan_warning_on_day_3():
    rows = tax.plan({"id": 1}, 3)
    assert len(rows) == 1
    assert rows[0]["kind"] == "tax" and rows[0]["phase"] == "warning"
    assert rows[0]["due_day"] == 3


def test_plan_collect_on_day_10():
    rows = tax.plan({"id": 1}, 10)
    assert any(r["phase"] == "collect" and r["due_day"] == 10
               and r["payload"]["amount"] == 1000 for r in rows)


def test_plan_collect_on_day_90():
    rows = tax.plan({"id": 1}, 90)
    assert any(r["phase"] == "collect" and r["due_day"] == 90 for r in rows)


def test_plan_no_collect_on_day_100():
    # MAX_DAY 이상의 collect는 plan하지 않는다
    rows = tax.plan({"id": 1}, 100)
    assert rows == []


def test_plan_no_op_on_other_days():
    assert tax.plan({"id": 1}, 5) == []
    assert tax.plan({"id": 1}, 11) == []


def test_evaluate_warning_not_failed_after_due():
    mission = {"id": 1, "kind": "tax", "phase": "warning", "due_day": 3, "status": "pending"}
    assert tax.evaluate({"id": 1, "current_day": 5}, 5, mission) == ("pending", None)


def test_evaluate_collect_due_passed_pending_fails():
    mission = {"id": 1, "kind": "tax", "phase": "collect", "due_day": 10,
               "status": "pending", "payload": {"amount": 1000}}
    status, ending = tax.evaluate({"id": 1, "current_day": 11}, 11, mission)
    assert status == "failed"
    assert ending == "mission_tax_unpaid"


def test_evaluate_collect_done_no_ending():
    mission = {"id": 1, "kind": "tax", "phase": "collect", "due_day": 10,
               "status": "done", "payload": {"amount": 1000}}
    assert tax.evaluate({"id": 1, "current_day": 11}, 11, mission) == ("done", None)


def test_slot_for_warning():
    s = tax.slot_for({"id": 7, "kind": "tax", "phase": "warning", "payload": {}})
    assert s == {"kind": "mission_npc", "mission_id": 7, "mission_kind": "tax",
                 "phase": "warning", "amount": 0}


def test_slot_for_collect_includes_amount():
    s = tax.slot_for({"id": 7, "kind": "tax", "phase": "collect",
                       "payload": {"amount": 1000}})
    assert s["amount"] == 1000


def test_on_action_warning_ack_marks_done(fake_repo, monkeypatch):
    monkeypatch.setattr(tax, "repo", fake_repo)
    fake_repo.players[1] = {"id": 1, "gold": 5000, "current_day": 3, "current_phase": "visitor"}
    m = fake_repo.insert_mission({"player_id": 1, "kind": "tax", "phase": "warning",
                                   "due_day": 3, "payload": {}})
    tax.on_action(fake_repo.players[1], m, "ack")
    assert fake_repo.get_mission(m["id"])["status"] == "done"


def test_on_action_collect_pay_success(fake_repo, monkeypatch):
    monkeypatch.setattr(tax, "repo", fake_repo)
    fake_repo.players[1] = {"id": 1, "gold": 5000, "current_day": 10, "current_phase": "visitor"}
    m = fake_repo.insert_mission({"player_id": 1, "kind": "tax", "phase": "collect",
                                   "due_day": 10, "payload": {"amount": 1000}})
    tax.on_action(fake_repo.players[1], m, "pay")
    assert fake_repo.players[1]["gold"] == 4000
    assert fake_repo.get_mission(m["id"])["status"] == "done"


def test_on_action_collect_pay_insufficient_gold_raises(fake_repo, monkeypatch):
    monkeypatch.setattr(tax, "repo", fake_repo)
    fake_repo.players[1] = {"id": 1, "gold": 500, "current_day": 10, "current_phase": "visitor"}
    m = fake_repo.insert_mission({"player_id": 1, "kind": "tax", "phase": "collect",
                                   "due_day": 10, "payload": {"amount": 1000}})
    with pytest.raises(ValueError):
        tax.on_action(fake_repo.players[1], m, "pay")
    # 골드는 그대로
    assert fake_repo.players[1]["gold"] == 500


def test_on_action_collect_skip_fails(fake_repo, monkeypatch):
    monkeypatch.setattr(tax, "repo", fake_repo)
    fake_repo.players[1] = {"id": 1, "gold": 5000, "current_day": 10, "current_phase": "visitor"}
    m = fake_repo.insert_mission({"player_id": 1, "kind": "tax", "phase": "collect",
                                   "due_day": 10, "payload": {"amount": 1000}})
    result = tax.on_action(fake_repo.players[1], m, "skip")
    assert result["ending_kind"] == "mission_tax_unpaid"
    assert fake_repo.get_mission(m["id"])["status"] == "failed"
```

- [ ] **Step 2: Run — should fail**

```bash
python -m pytest tests/test_mission_tax.py -v
```
Expected: 모두 fail (NotImplementedError 등).

- [ ] **Step 3: 구현**

```python
# backend/app/missions/tax.py
"""세금관 미션 — day 3 warning, day 10/20/.../90 collect 1000골드."""
from __future__ import annotations
from typing import Any
from .. import repo

AMOUNT = 1000
WARNING_DAY = 3
COLLECT_DAYS = {10, 20, 30, 40, 50, 60, 70, 80, 90}


def plan(player: dict[str, Any], day: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if day == WARNING_DAY:
        rows.append({"player_id": player["id"], "kind": "tax",
                      "phase": "warning", "due_day": day, "payload": {}})
    if day in COLLECT_DAYS:
        rows.append({"player_id": player["id"], "kind": "tax",
                      "phase": "collect", "due_day": day,
                      "payload": {"amount": AMOUNT}})
    return rows


def evaluate(player: dict[str, Any], day: int,
              mission: dict[str, Any]) -> tuple[str, str | None]:
    if mission["status"] != "pending":
        return (mission["status"], None)
    if mission["phase"] == "warning":
        return ("pending", None)  # 정보 전달용, slot 처리 후 done 되거나 그냥 남음
    # collect — 만기일 지났는데 미처리면 fail
    if day > int(mission["due_day"]):
        return ("failed", "mission_tax_unpaid")
    return ("pending", None)


def slot_for(mission: dict[str, Any]) -> dict[str, Any]:
    payload = mission.get("payload") or {}
    return {
        "kind": "mission_npc", "mission_id": mission["id"],
        "mission_kind": "tax", "phase": mission["phase"],
        "amount": int(payload.get("amount", 0)),
    }


def on_action(player: dict[str, Any], mission: dict[str, Any], action: str) -> dict[str, Any]:
    phase = mission["phase"]
    if phase == "warning":
        if action == "ack":
            repo.update_mission(mission["id"], status="done")
            return {"ok": True}
        raise ValueError(f"invalid action {action} for warning")
    # collect
    if action == "pay":
        amount = int((mission.get("payload") or {}).get("amount", AMOUNT))
        gold = int(player.get("gold", 0))
        if gold < amount:
            raise ValueError("insufficient_gold")
        repo.update_player(player["id"], gold=gold - amount)
        player["gold"] = gold - amount
        repo.update_mission(mission["id"], status="done")
        repo.insert_day_event(
            player["id"], day=player["current_day"], phase=player["current_phase"],
            kind="tax_paid", payload={"amount": amount, "mission_id": mission["id"]},
        )
        return {"ok": True, "paid": amount}
    if action == "skip":
        repo.update_mission(mission["id"], status="failed")
        return {"ok": True, "ending_kind": "mission_tax_unpaid"}
    raise ValueError(f"invalid action {action} for collect")
```

- [ ] **Step 4: Run — should pass**

```bash
python -m pytest tests/test_mission_tax.py -v
```
Expected: 모두 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/missions/tax.py backend/tests/test_mission_tax.py
git commit -m "feat(missions/tax): warning (day 3) + collect (day 10/20/.../90) with pay/skip actions"
```

---

### Task 6: 상인조합장 미션 (`league_chief.py`)

**Files:**
- Modify: `backend/app/missions/league_chief.py`
- Create: `backend/tests/test_mission_league_chief.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# backend/tests/test_mission_league_chief.py
import pytest
from app.missions import league_chief as lc


def test_spawn_day_in_range_and_deterministic():
    days = {lc.spawn_day(player_id=pid) for pid in range(50)}
    assert all(11 <= d <= 15 for d in days)
    assert lc.spawn_day(7) == lc.spawn_day(7)


def test_plan_inserts_challenge_on_spawn_day():
    pid = 1
    spawn = lc.spawn_day(pid)
    rows = lc.plan({"id": pid}, spawn)
    assert len(rows) == 1
    r = rows[0]
    assert r["kind"] == "league_chief" and r["phase"] == "challenge"
    assert r["payload"]["threshold"] == 50
    assert r["payload"]["deadline"] == spawn + 3


def test_plan_no_op_other_days():
    pid = 1
    spawn = lc.spawn_day(pid)
    assert lc.plan({"id": pid}, spawn - 1) == []
    assert lc.plan({"id": pid}, spawn + 1) == []


def test_evaluate_challenge_condition_met_inserts_praise(fake_repo, monkeypatch):
    monkeypatch.setattr(lc, "repo", fake_repo)
    pid = 1
    fake_repo.players[pid] = {"id": pid, "reputation": 50, "current_day": 13}
    mission = {"id": 5, "player_id": pid, "kind": "league_chief", "phase": "challenge",
               "due_day": 12, "status": "pending",
               "payload": {"threshold": 50, "deadline": 15}}
    status, ending = lc.evaluate(fake_repo.players[pid], 13, mission)
    assert status == "condition_met"
    assert ending is None
    # praise 미션이 다음날(due_day=14)에 insert됐는지
    praise = [m for m in fake_repo.missions
              if m["kind"] == "league_chief" and m["phase"] == "praise"]
    assert len(praise) == 1
    assert praise[0]["due_day"] == 14


def test_evaluate_challenge_under_threshold_keeps_pending(fake_repo, monkeypatch):
    monkeypatch.setattr(lc, "repo", fake_repo)
    fake_repo.players[1] = {"id": 1, "reputation": 30, "current_day": 13}
    mission = {"id": 5, "player_id": 1, "kind": "league_chief", "phase": "challenge",
               "due_day": 12, "status": "pending",
               "payload": {"threshold": 50, "deadline": 15}}
    status, ending = lc.evaluate(fake_repo.players[1], 13, mission)
    assert status == "pending"
    assert ending is None


def test_evaluate_challenge_deadline_passed_fails(fake_repo, monkeypatch):
    monkeypatch.setattr(lc, "repo", fake_repo)
    fake_repo.players[1] = {"id": 1, "reputation": 30, "current_day": 16}
    mission = {"id": 5, "player_id": 1, "kind": "league_chief", "phase": "challenge",
               "due_day": 12, "status": "pending",
               "payload": {"threshold": 50, "deadline": 15}}
    status, ending = lc.evaluate(fake_repo.players[1], 16, mission)
    assert status == "failed"
    assert ending == "mission_league_failed"


def test_on_action_challenge_ack(fake_repo, monkeypatch):
    monkeypatch.setattr(lc, "repo", fake_repo)
    fake_repo.players[1] = {"id": 1, "reputation": 30, "current_day": 12, "current_phase": "visitor"}
    m = fake_repo.insert_mission({"player_id": 1, "kind": "league_chief", "phase": "challenge",
                                   "due_day": 12, "payload": {"threshold": 50, "deadline": 15}})
    lc.on_action(fake_repo.players[1], m, "ack")
    # challenge ack은 status 변경 안 함 (evaluate가 조건 평가)
    assert fake_repo.get_mission(m["id"])["status"] == "pending"


def test_on_action_praise_ack_marks_done(fake_repo, monkeypatch):
    monkeypatch.setattr(lc, "repo", fake_repo)
    fake_repo.players[1] = {"id": 1, "reputation": 60, "current_day": 14, "current_phase": "visitor"}
    m = fake_repo.insert_mission({"player_id": 1, "kind": "league_chief", "phase": "praise",
                                   "due_day": 14, "payload": {}})
    lc.on_action(fake_repo.players[1], m, "ack")
    assert fake_repo.get_mission(m["id"])["status"] == "done"
```

- [ ] **Step 2: Run — should fail**

```bash
python -m pytest tests/test_mission_league_chief.py -v
```
Expected: FAIL.

- [ ] **Step 3: 구현**

```python
# backend/app/missions/league_chief.py
"""상인조합장 미션 — day 11~15 random spawn, d+3 안에 평판 50 도달."""
from __future__ import annotations
import random
from typing import Any
from .. import repo

THRESHOLD = 50
WINDOW_DAYS = 3


def spawn_day(player_id: int) -> int:
    seed = (player_id * 1_000_003 + 47) & 0xFFFFFFFF
    return random.Random(seed).randint(11, 15)


def plan(player: dict[str, Any], day: int) -> list[dict[str, Any]]:
    if day != spawn_day(player["id"]):
        return []
    return [{
        "player_id": player["id"], "kind": "league_chief",
        "phase": "challenge", "due_day": day,
        "payload": {"threshold": THRESHOLD, "deadline": day + WINDOW_DAYS},
    }]


def evaluate(player: dict[str, Any], day: int,
              mission: dict[str, Any]) -> tuple[str, str | None]:
    if mission["status"] != "pending":
        return (mission["status"], None)
    phase = mission["phase"]
    payload = mission.get("payload") or {}
    threshold = int(payload.get("threshold", THRESHOLD))
    if phase == "challenge":
        if int(player.get("reputation", 0)) >= threshold:
            # condition_met + praise 미션 insert (다음 날)
            repo.insert_mission({
                "player_id": player["id"], "kind": "league_chief",
                "phase": "praise", "due_day": day + 1, "payload": {},
            })
            return ("condition_met", None)
        deadline = int(payload.get("deadline", day + WINDOW_DAYS))
        if day > deadline:
            return ("failed", "mission_league_failed")
        return ("pending", None)
    if phase == "praise":
        # praise는 만기 지나도 fail 아님 — 그냥 done
        if day > int(mission["due_day"]):
            return ("done", None)
        return ("pending", None)
    return ("pending", None)


def slot_for(mission: dict[str, Any]) -> dict[str, Any]:
    payload = mission.get("payload") or {}
    return {
        "kind": "mission_npc", "mission_id": mission["id"],
        "mission_kind": "league_chief", "phase": mission["phase"],
        "threshold": int(payload.get("threshold", THRESHOLD)),
        "deadline": int(payload.get("deadline", 0)),
    }


def on_action(player: dict[str, Any], mission: dict[str, Any], action: str) -> dict[str, Any]:
    if action != "ack":
        raise ValueError(f"invalid action {action}")
    if mission["phase"] == "praise":
        repo.update_mission(mission["id"], status="done")
    # challenge ack은 status 유지 (evaluate가 조건으로 평가)
    return {"ok": True}
```

- [ ] **Step 4: Run — should pass**

```bash
python -m pytest tests/test_mission_league_chief.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/missions/league_chief.py backend/tests/test_mission_league_chief.py
git commit -m "feat(missions/league_chief): random spawn 11-15 + d+3 rep 50 challenge/praise"
```

---

### Task 7: 스케줄러 (`scheduler.py`)

**Files:**
- Create: `backend/app/missions/scheduler.py`
- Create: `backend/tests/test_mission_scheduler.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# backend/tests/test_mission_scheduler.py
import pytest
from app.missions import scheduler


def test_advance_plans_and_evaluates(fake_repo, monkeypatch):
    monkeypatch.setattr(scheduler, "repo", fake_repo)
    from app.missions import tax as tax_mod, league_chief as lc_mod
    monkeypatch.setattr(tax_mod, "repo", fake_repo)
    monkeypatch.setattr(lc_mod, "repo", fake_repo)

    fake_repo.players[1] = {"id": 1, "current_day": 3, "reputation": 0,
                             "current_phase": "forge_open", "gold": 5000,
                             "ending_kind": None}
    scheduler.advance(fake_repo.players[1])
    # day 3 warning이 들어가 있어야 함
    assert any(m["kind"] == "tax" and m["phase"] == "warning"
               for m in fake_repo.missions)


def test_advance_ending_triggered_on_unpaid_tax(fake_repo, monkeypatch):
    monkeypatch.setattr(scheduler, "repo", fake_repo)
    from app.missions import tax as tax_mod
    from app import endgame
    monkeypatch.setattr(tax_mod, "repo", fake_repo)
    monkeypatch.setattr(endgame, "repo", fake_repo)

    fake_repo.players[1] = {"id": 1, "current_day": 11, "reputation": 0,
                             "current_phase": "forge_open", "gold": 500,
                             "ending_kind": None}
    # 미납 collect 미션 prior insert
    fake_repo.insert_mission({"player_id": 1, "kind": "tax", "phase": "collect",
                               "due_day": 10, "status": "pending",
                               "payload": {"amount": 1000}})
    scheduler.advance(fake_repo.players[1])
    assert fake_repo.players[1]["ending_kind"] == "mission_tax_unpaid"


def test_today_slots_returns_due_today_missions(fake_repo, monkeypatch):
    monkeypatch.setattr(scheduler, "repo", fake_repo)
    fake_repo.insert_mission({"player_id": 1, "kind": "tax", "phase": "warning",
                               "due_day": 3, "status": "pending", "payload": {}})
    fake_repo.insert_mission({"player_id": 1, "kind": "tax", "phase": "collect",
                               "due_day": 10, "status": "pending",
                               "payload": {"amount": 1000}})
    slots = scheduler.today_slots(player_id=1, day=3)
    assert len(slots) == 1
    assert slots[0]["mission_kind"] == "tax"
    assert slots[0]["phase"] == "warning"
```

- [ ] **Step 2: Run — should fail (module missing)**

```bash
python -m pytest tests/test_mission_scheduler.py -v
```
Expected: ImportError.

- [ ] **Step 3: 구현**

```python
# backend/app/missions/scheduler.py
"""미션 스케줄러 — forge_open에서 plan → evaluate → endgame, today_slots 제공."""
from __future__ import annotations
from typing import Any
from .. import repo, endgame
from . import MODULES, module_for


def advance(player: dict[str, Any]) -> None:
    """현재 day 기준 plan + evaluate. ending 발생 시 endgame.apply_ending 호출 후 종료."""
    day = int(player["current_day"])
    pid = player["id"]

    # 1) Plan — 각 모듈이 오늘 등장할 미션 행 insert
    for kind, mod in MODULES.items():
        for row in mod.plan(player, day):
            repo.insert_mission(row)

    # 2) Evaluate — 모든 pending 미션 재평가
    for mission in repo.list_pending_missions(pid):
        mod = module_for(mission["kind"])
        new_status, ending_kind = mod.evaluate(player, day, mission)
        if new_status != mission["status"]:
            repo.update_mission(mission["id"], status=new_status)
        if ending_kind:
            endgame.apply_ending(pid, ending_kind)
            player["ending_kind"] = ending_kind
            return

    # 3) Follow-up plan (condition_met 처리 직후 새 phase 미션이 생긴 케이스는
    #    evaluate 안에서 이미 insert됨. 추가 plan 패스 없음.)


def today_slots(player_id: int, day: int) -> list[dict[str, Any]]:
    """오늘 due_day인 pending 미션을 day_schedule용 슬롯으로 변환."""
    missions = repo.list_missions_today(player_id, day)
    return [module_for(m["kind"]).slot_for(m) for m in missions]
```

- [ ] **Step 4: `endgame.apply_ending` 시그니처 확인**

Run: `grep -n "def apply_ending" /home/afraidnot/dev/smith-tycoon/.claude/worktrees/async-combat/backend/app/endgame.py`

기존 시그니처가 `apply_ending(player_id, ending_kind)` 형태인지 확인. 이미 그렇다면 OK. 새 ending 종류는 데이터 무관, 단순히 `players.ending_kind` 문자열에 저장만 한다 (constants 등록 필요 없음 — 다음 태스크에서 확인).

- [ ] **Step 5: Run + commit**

```bash
python -m pytest tests/test_mission_scheduler.py -v
```
Expected: PASS.

```bash
git add backend/app/missions/scheduler.py backend/tests/test_mission_scheduler.py
git commit -m "feat(missions/scheduler): advance plans+evaluates+triggers endgame; today_slots emits slot rows"
```

---

### Task 8: endgame에 새 ending kind 등록

**Files:**
- Modify: `backend/app/endgame.py` (필요 시)

- [ ] **Step 1: 현재 ending kind enum/리스트 확인**

Run: `grep -n "ending_kind\|ENDINGS\|VALID_ENDINGS\|mission_" backend/app/endgame.py | head -20`

만약 검증 enum이 있다면 두 종류 추가. 없으면 (텍스트 컬럼이라) skip 가능.

- [ ] **Step 2: apply_ending이 미션 endings 그대로 받아들이는지 빠른 테스트**

```python
# 임시 sanity check (테스트 추가 안 함, 콘솔만)
python -c "
from unittest.mock import MagicMock
from app import endgame
import app.endgame as e
fake = MagicMock()
e.repo = fake
endgame.apply_ending(1, 'mission_tax_unpaid')
print(fake.update_player.call_args)
"
```
Expected: `call(1, ending_kind='mission_tax_unpaid', current_phase='game_over')` 같은 호출. 호출되면 OK.

만약 검증 로직이 막아세우면 거기에 `mission_tax_unpaid`, `mission_league_failed` 추가.

- [ ] **Step 3: Commit (변경 있을 때만)**

```bash
git add -A
git commit -m "feat(endgame): register mission_tax_unpaid + mission_league_failed kinds"
```

(변경 없으면 skip.)

---

### Task 9: day_open 통합 — missions 슬롯 prepend

**Files:**
- Modify: `backend/app/day_open.py`
- Modify: `backend/tests/test_day_open.py`

- [ ] **Step 1: day_open.prepare_day 수정**

```python
# backend/app/day_open.py 의 prepare_day 시작 부분에:
from .missions import scheduler as mission_scheduler

def prepare_day(player):
    pid = player["id"]
    day = int(player["current_day"])

    # 1) 미션 스케줄러 — plan + evaluate + endgame
    mission_scheduler.advance(player)
    if player.get("ending_kind"):
        # ending 발동 → schedule 만들지 않음
        return {"schedule": [], "death_mails": []}

    # 2) 기존 흐름 (pending_outcomes 등)
    ... (기존 로직)

    # 마지막 schedule 조합 직전:
    mission_slots = mission_scheduler.today_slots(pid, day)
    schedule = mission_slots + schedule   # prepend

    repo.update_player(pid, day_schedule=schedule, current_visitor_index=0)
    player["day_schedule"] = schedule
    player["current_visitor_index"] = 0
    return {"schedule": schedule, "death_mails": death_mails}
```

정확한 위치는 기존 `prepare_day` 본문을 따라 적용. 미션 슬롯 prepend는 schedule 저장 직전.

- [ ] **Step 2: 테스트 추가** (`backend/tests/test_day_open.py`)

기존 파일 끝에 append:

```python
@pytest.mark.asyncio
async def test_prepare_day_prepends_mission_slot(fake_repo, monkeypatch):
    from app import day_open
    from app.missions import scheduler, tax
    monkeypatch.setattr(day_open, "repo", fake_repo)
    monkeypatch.setattr(scheduler, "repo", fake_repo)
    monkeypatch.setattr(tax, "repo", fake_repo)
    monkeypatch.setattr(day_open, "hero_registry",
                         type("X", (), {"heroes_for_today": staticmethod(lambda pid, d, count=3: [])})())

    fake_repo.players[1] = {"id": 1, "current_day": 3, "reputation": 0,
                             "current_phase": "forge_open", "gold": 5000,
                             "ending_kind": None}
    result = day_open.prepare_day(fake_repo.players[1])
    # 첫 슬롯이 mission_npc (tax warning)
    assert len(result["schedule"]) > 0
    assert result["schedule"][0]["kind"] == "mission_npc"
    assert result["schedule"][0]["mission_kind"] == "tax"


def test_prepare_day_skips_when_ending_triggered(fake_repo, monkeypatch):
    from app import day_open
    from app.missions import scheduler, tax
    from app import endgame
    for mod in (day_open, scheduler, tax, endgame):
        monkeypatch.setattr(mod, "repo", fake_repo)

    fake_repo.players[1] = {"id": 1, "current_day": 11, "reputation": 0,
                             "current_phase": "forge_open", "gold": 0,
                             "ending_kind": None}
    fake_repo.insert_mission({"player_id": 1, "kind": "tax", "phase": "collect",
                               "due_day": 10, "status": "pending",
                               "payload": {"amount": 1000}})
    result = day_open.prepare_day(fake_repo.players[1])
    assert fake_repo.players[1]["ending_kind"] == "mission_tax_unpaid"
    assert result["schedule"] == []
```

- [ ] **Step 3: Run + commit**

```bash
python -m pytest tests/test_day_open.py -v
```
Expected: PASS.

```bash
git add backend/app/day_open.py backend/tests/test_day_open.py
git commit -m "feat(day-open): prepend mission slots; bail out when ending triggered"
```

---

### Task 10: `/visitor/current/mission_action` 엔드포인트

**Files:**
- Create: `backend/app/api/mission.py`
- Create: `backend/tests/test_api_mission_action.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/visitor.py` (skip을 mission slot에서 on_action 거치게)

- [ ] **Step 1: 엔드포인트 구현**

```python
# backend/app/api/mission.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from .. import repo, state_machine, endgame
from ..auth import current_player
from ..missions import module_for
from ..api.visitor import advance as advance_visitor_phase

router = APIRouter(tags=["mission"])


class ActionReq(BaseModel):
    action: str  # "pay" | "ack" | "skip"


def _current_mission(player: dict) -> dict:
    try:
        state_machine.assert_phase(player["current_phase"], "visitor")
    except state_machine.PhaseError:
        raise HTTPException(400, detail={"error": "wrong_phase"})
    sched = player.get("day_schedule") or []
    idx = player.get("current_visitor_index", 0)
    if idx >= len(sched):
        raise HTTPException(409, "no current visitor")
    slot = sched[idx]
    if slot["kind"] != "mission_npc":
        raise HTTPException(409, "current slot is not a mission_npc")
    mission = repo.get_mission(int(slot["mission_id"]))
    if not mission:
        raise HTTPException(404, "mission not found")
    return mission


@router.post("/visitor/current/mission_action")
def post_mission_action(req: ActionReq, player: dict = Depends(current_player)):
    mission = _current_mission(player)
    mod = module_for(mission["kind"])
    try:
        result = mod.on_action(player, mission, req.action)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "invalid_action", "message": str(e)})
    ending = result.get("ending_kind")
    if ending:
        endgame.apply_ending(player["id"], ending)
        return {"ok": True, "ending": ending}
    player = repo.load_player(player["id"])
    if player["current_phase"] == "visitor":
        advance_visitor_phase(player)
    return {"ok": True, "current_phase": player["current_phase"]}
```

- [ ] **Step 2: main.py 라우터 등록**

```python
from .api import ..., mission as mission_api
app.include_router(mission_api.router)
```

- [ ] **Step 3: visitor.py skip이 mission slot이면 on_action 거치게**

`backend/app/api/visitor.py`의 `skip_visitor` 핸들러를 다음과 같이 수정:

```python
@router.post("/current/skip")
def skip_visitor(player: dict = Depends(current_player)):
    slot = _current_slot(player)
    if slot["kind"] == "mission_npc":
        from .. import repo, endgame
        from ..missions import module_for
        mission = repo.get_mission(int(slot["mission_id"]))
        if mission:
            mod = module_for(mission["kind"])
            try:
                result = mod.on_action(player, mission, "skip")
            except ValueError:
                raise HTTPException(400, "skip not supported for this mission slot")
            ending = result.get("ending_kind")
            if ending:
                endgame.apply_ending(player["id"], ending)
                return {"ok": True, "ending": ending}
    return {"ok": True, **advance(player)}
```

- [ ] **Step 4: API 통합 테스트**

```python
# backend/tests/test_api_mission_action.py
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def patched_app(fake_repo):
    from app import auth as auth_mod
    from app.api import mission as mission_api
    from app.api import visitor as visitor_api
    from app import repo as real_repo, endgame
    from app.missions import tax, league_chief, scheduler

    fake_repo.players[1] = {"id": 1, "nickname": "tester", "current_day": 10,
                             "current_phase": "visitor", "current_visitor_index": 0,
                             "reputation": 0, "gold": 5000,
                             "day_schedule": [], "ending_kind": None}
    fake_repo.get_or_create_player_by_nickname = lambda nick: fake_repo.players[1]

    with patch.object(mission_api, "repo", fake_repo), \
         patch.object(visitor_api, "repo", fake_repo), \
         patch.object(real_repo, "_client", side_effect=AssertionError("no real client")), \
         patch.object(auth_mod, "repo", fake_repo), \
         patch.object(endgame, "repo", fake_repo), \
         patch.object(tax, "repo", fake_repo), \
         patch.object(league_chief, "repo", fake_repo), \
         patch.object(scheduler, "repo", fake_repo):
        from app.main import app
        yield TestClient(app), fake_repo


def test_pay_tax_success(patched_app):
    client, fake = patched_app
    m = fake.insert_mission({"player_id": 1, "kind": "tax", "phase": "collect",
                              "due_day": 10, "status": "pending",
                              "payload": {"amount": 1000}})
    fake.players[1]["day_schedule"] = [{
        "kind": "mission_npc", "mission_id": m["id"],
        "mission_kind": "tax", "phase": "collect", "amount": 1000,
    }]
    r = client.post("/visitor/current/mission_action",
                    json={"action": "pay"},
                    headers={"X-Player-Nickname": "tester"})
    assert r.status_code == 200, r.text
    assert fake.players[1]["gold"] == 4000
    assert fake.get_mission(m["id"])["status"] == "done"


def test_pay_tax_insufficient_returns_400(patched_app):
    client, fake = patched_app
    fake.players[1]["gold"] = 500
    m = fake.insert_mission({"player_id": 1, "kind": "tax", "phase": "collect",
                              "due_day": 10, "status": "pending",
                              "payload": {"amount": 1000}})
    fake.players[1]["day_schedule"] = [{
        "kind": "mission_npc", "mission_id": m["id"],
        "mission_kind": "tax", "phase": "collect", "amount": 1000,
    }]
    r = client.post("/visitor/current/mission_action",
                    json={"action": "pay"},
                    headers={"X-Player-Nickname": "tester"})
    assert r.status_code == 400


def test_skip_tax_collect_triggers_ending(patched_app):
    client, fake = patched_app
    m = fake.insert_mission({"player_id": 1, "kind": "tax", "phase": "collect",
                              "due_day": 10, "status": "pending",
                              "payload": {"amount": 1000}})
    fake.players[1]["day_schedule"] = [{
        "kind": "mission_npc", "mission_id": m["id"],
        "mission_kind": "tax", "phase": "collect", "amount": 1000,
    }]
    r = client.post("/visitor/current/mission_action",
                    json={"action": "skip"},
                    headers={"X-Player-Nickname": "tester"})
    assert r.status_code == 200
    assert fake.players[1].get("ending_kind") == "mission_tax_unpaid"


def test_warning_ack_advances(patched_app):
    client, fake = patched_app
    fake.players[1]["current_day"] = 3
    m = fake.insert_mission({"player_id": 1, "kind": "tax", "phase": "warning",
                              "due_day": 3, "status": "pending", "payload": {}})
    fake.players[1]["day_schedule"] = [
        {"kind": "mission_npc", "mission_id": m["id"],
         "mission_kind": "tax", "phase": "warning", "amount": 0},
        {"kind": "new_hero", "hero_id": 999},
    ]
    r = client.post("/visitor/current/mission_action",
                    json={"action": "ack"},
                    headers={"X-Player-Nickname": "tester"})
    assert r.status_code == 200
    assert fake.players[1]["current_visitor_index"] == 1
```

- [ ] **Step 5: Run + commit**

```bash
python -m pytest tests/test_api_mission_action.py -v
```
Expected: PASS.

```bash
git add -A
git commit -m "feat(api): /visitor/current/mission_action + visitor/skip handles mission slots"
```

---

### Task 11: /state hydrate — mission payload 펼치기

**Files:**
- Modify: `backend/app/api/state.py`

- [ ] **Step 1: `_hydrate_visitor`에 분기 추가**

기존 `kind == "merchant"` 분기 다음에:

```python
elif kind == "mission_npc":
    # 이미 slot 자체에 mission_kind/phase/amount/threshold/deadline이 들어있다.
    # 펼침은 dict(slot)로 이미 끝나 있으니 추가 작업 없음.
    pass
```

(특별 처리 필요 없음 — slot에 이미 payload가 있음. 명시적 분기로 두는 게 의도 표현.)

- [ ] **Step 2: Import check + commit**

```bash
python -c "from app.api.state import _hydrate_visitor; print('OK')"
git add backend/app/api/state.py
git commit -m "feat(state): explicit mission_npc hydration branch (slot fields already present)"
```

(변경 미미할 수 있음 — slot에 이미 들어있으면 commit skip.)

---

### Task 12: 프론트엔드 — 타입 + API 래퍼 + endings

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/endings.ts`

- [ ] **Step 1: types.ts**

```typescript
// VisitorKind enum에 추가
export type VisitorKind = "new_hero" | "returning_hero" | "merchant" | "mission_npc";

// CurrentVisitor에 mission 필드 추가
export interface CurrentVisitor {
  kind: VisitorKind;
  hero_id?: number;
  outcome_id?: number;
  hero?: Hero;
  outcome?: BattleOutcome;
  weapon_snapshot?: WeaponSnapshot;
  depart_day?: number;
  recap?: string;
  merchant?: MerchantToday;
  // mission_npc
  mission_id?: number;
  mission_kind?: "tax" | "league_chief";
  phase?: string;
  amount?: number;
  threshold?: number;
  deadline?: number;
}
```

(이미 일부 필드는 있을 수 있음 — 중복 없게 병합.)

- [ ] **Step 2: api.ts 래퍼**

`api` 객체에 추가:
```typescript
visitorMissionAction: (action: "pay" | "ack" | "skip") =>
  request<{ ok: true; current_phase?: string; ending?: string }>(
    "POST", "/visitor/current/mission_action", { action }),
```

- [ ] **Step 3: endings.ts 추가**

기존 매핑에 두 줄 추가:
```typescript
mission_tax_unpaid: "세금 미납으로 마을에서 쫓겨났다",
mission_league_failed: "상인조합장의 인정을 못 받아 가게가 강제 폐업",
```

- [ ] **Step 4: tsc + commit**

```bash
cd frontend && npx tsc --noEmit
git add frontend/src/types.ts frontend/src/api.ts frontend/src/endings.ts
git commit -m "feat(frontend): types/api/endings for mission_npc"
```

---

### Task 13: MissionPanel + VisitorRouter 분기

**Files:**
- Create: `frontend/src/missions.ts`
- Create: `frontend/src/components/MissionPanel.tsx`
- Modify: `frontend/src/components/VisitorRouter.tsx`

- [ ] **Step 1: missions.ts 메시지/액션 매핑**

```typescript
// frontend/src/missions.ts
export type MissionKind = "tax" | "league_chief";
export type MissionPhase = "warning" | "collect" | "challenge" | "praise";

export const MISSION_TITLE: Record<MissionKind, string> = {
  tax: "세금 징수관",
  league_chief: "한자 상인조합장",
};

export const MISSION_MESSAGE: Record<MissionKind, Partial<Record<MissionPhase, string>>> = {
  tax: {
    warning: "이 마을은 세금을 매기지! 열흘 뒤 다시 와서 1000골드 받아간다. 그때 안 내면 알지?",
    collect: "오늘이 그날이다. 1000골드 내놔라. 못 내면 끝장이다.",
  },
  league_chief: {
    challenge: "한자 상인조합장이다. 너 같은 무명 대장장이가 우리 도시에서 장사하려면 평판 50은 찍어야지. 3일 안에 못 보이면 가게 닫게 만들 거다.",
    praise: "고생했다, 대장장이. 인정해주마. 잘 해 봐라.",
  },
};

export interface MissionAction {
  label: string;
  action: "pay" | "ack" | "skip";
  variantDanger?: boolean;
}

export function actionsFor(kind: MissionKind, phase: MissionPhase, playerGold: number, amount: number): MissionAction[] {
  if (kind === "tax" && phase === "warning") {
    return [{ label: "알겠다", action: "ack" }];
  }
  if (kind === "tax" && phase === "collect") {
    return [
      { label: `${amount}골드 상납하기`, action: "pay" },
      { label: "도망간다 (게임오버)", action: "skip", variantDanger: true },
    ];
  }
  return [{ label: "알겠다", action: "ack" }];
}
```

- [ ] **Step 2: MissionPanel**

```tsx
// frontend/src/components/MissionPanel.tsx
import { useState } from "react";
import type { CurrentVisitor, Player } from "../types";
import { api } from "../api";
import {
  MISSION_TITLE, MISSION_MESSAGE, actionsFor,
  MissionKind, MissionPhase,
} from "../missions";

export function MissionPanel({
  visitor, player, refresh,
}: { visitor: CurrentVisitor; player: Player; refresh: () => void }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const kind = visitor.mission_kind as MissionKind;
  const phase = (visitor.phase ?? "") as MissionPhase;
  const amount = visitor.amount ?? 0;
  const title = MISSION_TITLE[kind] ?? "미션 NPC";
  const msg = MISSION_MESSAGE[kind]?.[phase] ?? "...";
  const actions = actionsFor(kind, phase, player.gold, amount);

  const doAction = async (action: "pay" | "ack" | "skip") => {
    setBusy(true); setErr(null);
    try {
      await api.visitorMissionAction(action);
      refresh();
    } catch (e) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  return (
    <div>
      <h2>{title}</h2>
      <p style={{ whiteSpace: "pre-wrap" }}>{msg}</p>
      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
        {actions.map((a, i) => {
          const disabled = busy || (a.action === "pay" && player.gold < amount);
          return (
            <button key={i} className="btn"
                    style={a.variantDanger ? { color: "crimson" } : undefined}
                    disabled={disabled}
                    onClick={() => doAction(a.action)}>
              {a.label}
            </button>
          );
        })}
      </div>
      {err && <p style={{ color: "crimson" }}>{err}</p>}
    </div>
  );
}
```

- [ ] **Step 3: VisitorRouter 분기**

```tsx
// VisitorRouter.tsx
import { MissionPanel } from "./MissionPanel";

// 기존 분기들 사이에:
if (v.kind === "mission_npc") {
  return <MissionPanel key={slotKey} visitor={v} player={state.player!} refresh={refresh} />;
}
```

- [ ] **Step 4: tsc + commit**

```bash
cd frontend && npx tsc --noEmit
git add frontend/src/missions.ts frontend/src/components/MissionPanel.tsx frontend/src/components/VisitorRouter.tsx
git commit -m "feat(frontend): MissionPanel + VisitorRouter mission_npc branch"
```

---

### Task 14: 회귀 + 마이그레이션 적용 가이드 + 수동 검증

- [ ] **Step 1: 전체 백엔드 테스트**

```bash
cd backend && source .venv/bin/activate && python -m pytest -q
```
Expected: 모두 PASS (210 + 신규 약 25 = ~235).

- [ ] **Step 2: 프론트 tsc**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: 마이그레이션 012 적용 안내**

Supabase MCP `apply_migration` (또는 Studio SQL Editor)로 `backend/migrations/012_missions.sql` 적용.

- [ ] **Step 4: 브라우저 수동 시나리오**

1. 새 닉네임으로 게임 시작
2. day 3 진입 → 첫 슬롯이 세금관 warning. "알겠다" → advance.
3. day 10 진입 → 첫 슬롯 세금관 collect. 골드 ≥ 1000면 "상납" 가능. 골드 부족 시 disabled.
4. "도망간다" 누르면 게임오버 (mission_tax_unpaid).
5. 평판 빨리 올려서 spawn_day (11~15 중 하나)에 상인조합장 challenge → 평판 50 도달 → 다음날 praise.
6. 평판 50 못 채우면 day spawn+4에 게임오버 (mission_league_failed).

- [ ] **Step 5: 최종 commit (있으면)**

```bash
git status
```

---

## 자가 점검

**Spec coverage:**
- 마이그레이션 012 (missions 테이블) → Task 1
- repo CRUD → Task 3
- FakeRepo 확장 → Task 2
- 미션 모듈 인터페이스/레지스트리 → Task 4
- tax 모듈 → Task 5
- league_chief 모듈 → Task 6
- scheduler (advance + today_slots + ending 트리거) → Task 7
- endgame 새 ending kind → Task 8
- day_open prepend + ending skip → Task 9
- /visitor/current/mission_action + visitor/skip 통합 → Task 10
- /state hydrate → Task 11
- 프론트 types/api/endings → Task 12
- MissionPanel + VisitorRouter → Task 13
- 회귀 + 수동 → Task 14

**Out of scope (스펙대로):**
- 추가 미션, 보상 시스템, 캘린더 UI, 4차 배치 항목

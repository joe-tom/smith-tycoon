# Plan 4: 보스 + 5행 상성 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 7대 죄악 중간보스 + 최종보스 수르트를 일반 적과 같은 슬롯에서 확률적으로 등장시키고, 5행 상성으로 무기 데미지를 보정한다.

**Architecture:** 보스 정의는 코드 상수(`bosses.py`)로 두고 처치 이력은 `day_events.kind='boss_kill'`로 기록. `combat.roll_demon`을 확장해 day별 확률·약→강 순서로 보스를 굴리고, 5행 사이클(`금→바람→흙→물→불→금`)을 `decide_outcomes`의 power 계산에 1.3/0.7 보정으로 적용.

**Tech Stack:** Python (FastAPI, Pytest), Supabase Postgres (변경 없음 — DB 마이그레이션 없음), React/Vite.

**Spec:** `docs/superpowers/specs/2026-05-26-bosses-and-attribute-design.md`

---

## Phase 1 — 보스 정의 + 헬퍼

### Task 1.1: `bosses.py` 모듈 (TDD)

**Files:**
- Create: `backend/app/bosses.py`
- Create: `backend/tests/test_bosses.py`

- [ ] **Step 1: 실패 테스트**

```python
# backend/tests/test_bosses.py
from app.bosses import MID_BOSSES, FINAL_BOSS, weakest_alive, find_boss_by_id, is_boss_demon


def test_mid_bosses_count_and_order():
    assert len(MID_BOSSES) == 7
    diffs = [b["difficulty"] for b in MID_BOSSES]
    assert diffs == sorted(diffs), "MID_BOSSES must be sorted weakest first"


def test_all_bosses_have_required_fields():
    for b in MID_BOSSES + [FINAL_BOSS]:
        assert "boss_id" in b and "name" in b and "attribute" in b and "difficulty" in b


def test_weakest_alive_empty_defeated():
    assert weakest_alive(set())["boss_id"] == "belphegor"


def test_weakest_alive_first_killed():
    assert weakest_alive({"belphegor"})["boss_id"] == "beelzebub"


def test_weakest_alive_all_killed_returns_none():
    all_ids = {b["boss_id"] for b in MID_BOSSES}
    assert weakest_alive(all_ids) is None


def test_find_boss_by_id():
    assert find_boss_by_id("satan")["name"] == "사탄"
    assert find_boss_by_id("surt")["name"] == "수르트"
    assert find_boss_by_id("nonexistent") is None


def test_is_boss_demon_true_for_boss():
    assert is_boss_demon({"type": "사탄", "is_boss": True}) is True


def test_is_boss_demon_false_for_regular():
    assert is_boss_demon({"type": "고블린"}) is False
```

- [ ] **Step 2: 실패 확인**

```bash
cd /home/afraidnot/dev/smith-tycoon/backend && source .venv/bin/activate && python -m pytest tests/test_bosses.py -v
```
Expected: ImportError (`bosses` module not found).

- [ ] **Step 3: 구현**

```python
# backend/app/bosses.py
"""7대 죄악 중간보스 + 최종보스 수르트 정의."""
from __future__ import annotations
from typing import Any

# 약 → 강 순서 (등장·선택 순서로 사용)
MID_BOSSES: list[dict[str, Any]] = [
    {"boss_id": "belphegor", "name": "벨페고르",     "sin": "나태", "attribute": "흙",   "difficulty": 70},
    {"boss_id": "beelzebub", "name": "벨제붑",       "sin": "폭식", "attribute": "바람", "difficulty": 75},
    {"boss_id": "mammon",    "name": "맘몬",         "sin": "탐욕", "attribute": "금",   "difficulty": 78},
    {"boss_id": "leviathan", "name": "레비아탄",     "sin": "질투", "attribute": "물",   "difficulty": 82},
    {"boss_id": "asmodeus",  "name": "아스모데우스", "sin": "색욕", "attribute": "불",   "difficulty": 85},
    {"boss_id": "satan",     "name": "사탄",         "sin": "분노", "attribute": "불",   "difficulty": 90},
    {"boss_id": "lucifer",   "name": "루시퍼",       "sin": "교만", "attribute": "금",   "difficulty": 95},
]

FINAL_BOSS: dict[str, Any] = {
    "boss_id": "surt", "name": "수르트", "sin": None, "attribute": "불", "difficulty": 110,
}


def weakest_alive(defeated_ids: set[str]) -> dict[str, Any] | None:
    """MID_BOSSES 중 defeated_ids에 없는 첫 번째 (가장 약한) 보스."""
    for b in MID_BOSSES:
        if b["boss_id"] not in defeated_ids:
            return b
    return None


def find_boss_by_id(boss_id: str) -> dict[str, Any] | None:
    for b in MID_BOSSES:
        if b["boss_id"] == boss_id:
            return b
    if FINAL_BOSS["boss_id"] == boss_id:
        return FINAL_BOSS
    return None


def is_boss_demon(demon: dict[str, Any]) -> bool:
    return bool(demon.get("is_boss"))
```

- [ ] **Step 4: 통과 확인**

```bash
python -m pytest tests/test_bosses.py -v
```
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add backend/app/bosses.py backend/tests/test_bosses.py && git commit -m "feat(bosses): 7 sins + 수르트 definitions + helpers

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase 2 — 5행 상성 보정

### Task 2.1: `attribute_bonus` (TDD)

**Files:**
- Modify: `backend/app/combat.py`
- Create: `backend/tests/test_attribute_bonus.py`

- [ ] **Step 1: 실패 테스트**

```python
# backend/tests/test_attribute_bonus.py
import pytest
from app.combat import attribute_bonus


# 사이클: 금 → 바람 → 흙 → 물 → 불 → 금
# weapon이 demon을 억제하면 1.3, 역이면 0.7, 그 외 1.0
@pytest.mark.parametrize("weapon,demon,expected", [
    ("금",   "바람", 1.3),
    ("바람", "흙",   1.3),
    ("흙",   "물",   1.3),
    ("물",   "불",   1.3),
    ("불",   "금",   1.3),
    ("바람", "금",   0.7),
    ("흙",   "바람", 0.7),
    ("물",   "흙",   0.7),
    ("불",   "물",   0.7),
    ("금",   "불",   0.7),
    ("금",   "금",   1.0),
    ("금",   "물",   1.0),
    ("바람", "물",   1.0),
    (None,   "불",   1.0),
    ("불",   None,   1.0),
    (None,   None,   1.0),
])
def test_attribute_bonus(weapon, demon, expected):
    assert attribute_bonus(weapon, demon) == pytest.approx(expected)
```

- [ ] **Step 2: 실패 확인**

```bash
python -m pytest tests/test_attribute_bonus.py -v
```
Expected: ImportError (`attribute_bonus` not in combat).

- [ ] **Step 3: 구현 — `backend/app/combat.py`에 추가**

상단 (`DEMONS` 선언 직전 위치)에:

```python
# 5행 상성 사이클: 금 → 바람 → 흙 → 물 → 불 → 금 (각 원소가 다음을 억제)
CYCLE_NEXT = {"금": "바람", "바람": "흙", "흙": "물", "물": "불", "불": "금"}


def attribute_bonus(weapon_attr: str | None, demon_attr: str | None) -> float:
    """무기가 적 속성을 억제하면 1.3, 역이면 0.7, 그 외 1.0."""
    if not weapon_attr or not demon_attr:
        return 1.0
    if CYCLE_NEXT.get(weapon_attr) == demon_attr:
        return 1.3
    if CYCLE_NEXT.get(demon_attr) == weapon_attr:
        return 0.7
    return 1.0
```

- [ ] **Step 4: 통과 확인**

```bash
python -m pytest tests/test_attribute_bonus.py -v
```
Expected: 16 passed.

- [ ] **Step 5: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add backend/app/combat.py backend/tests/test_attribute_bonus.py && git commit -m "feat(combat): 5행 attribute_bonus (1.3 / 0.7 / 1.0)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 2.2: `decide_outcomes`에서 attribute_bonus 적용

**Files:**
- Modify: `backend/app/combat.py` (`decide_outcomes` 함수)

- [ ] **Step 1: 실패 테스트 추가**

`backend/tests/test_combat.py` 끝에:

```python
def test_decide_outcomes_attribute_advantage_helps():
    """Same hero/weapon/demon, but advantageous attribute → higher survival ratio."""
    from app.combat import decide_outcomes
    hero = {"str": 10, "mag": 5}
    demon_weak = {"type": "x", "attribute": "불", "difficulty": 30}
    weapon_good = {"sharpness": 50, "rarity": 30, "attribute": "물"}   # 물→불 억제 1.3
    weapon_bad  = {"sharpness": 50, "rarity": 30, "attribute": "불"}   # 동일속성 1.0
    survive_good = sum(1 for s in range(50)
                       if decide_outcomes(hero, weapon_good, demon_weak, seed=s)["hero"] == "survived")
    survive_bad = sum(1 for s in range(50)
                      if decide_outcomes(hero, weapon_bad,  demon_weak, seed=s)["hero"] == "survived")
    assert survive_good > survive_bad, f"good={survive_good} bad={survive_bad}"
```

- [ ] **Step 2: 실패 확인 (현재 decide_outcomes는 attribute 무시)**

```bash
python -m pytest tests/test_combat.py::test_decide_outcomes_attribute_advantage_helps -v
```
Expected: AssertionError 또는 동률.

- [ ] **Step 3: `decide_outcomes` 수정**

`backend/app/combat.py`의 `decide_outcomes` 본문 시작 부분(power 계산 직후)에 attribute_bonus 적용:

```python
def decide_outcomes(hero, weapon, demon, seed=None):
    rng = random.Random(seed)
    power = hero_power(hero, weapon)
    weapon_attr = weapon.get("attribute") if weapon else None
    power *= attribute_bonus(weapon_attr, demon.get("attribute"))
    threat = demon_threat(demon)
    ratio = (power / threat) * rng.uniform(0.75, 1.25)
    # ... 기존 ratio 분기 그대로
```

(이 함수의 나머지 분기는 변경 없음.)

- [ ] **Step 4: 통과 + 회귀 없음 확인**

```bash
python -m pytest tests/test_combat.py tests/test_attribute_bonus.py -v
```
Expected: 모두 PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add backend/app/combat.py backend/tests/test_combat.py && git commit -m "feat(combat): apply 5행 bonus to power in decide_outcomes

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase 3 — 보스 스폰 로직

### Task 3.1: `boss_spawn_chance` (TDD)

**Files:**
- Modify: `backend/app/combat.py`
- Create: `backend/tests/test_boss_spawn.py`

- [ ] **Step 1: 실패 테스트**

```python
# backend/tests/test_boss_spawn.py
import pytest
from app.combat import boss_spawn_chance


@pytest.mark.parametrize("day,expected", [
    (1, 0.0), (39, 0.0),
    (40, 0.05), (59, 0.05),
    (60, 0.10), (79, 0.10),
    (80, 0.25), (89, 0.25),
    (90, 1.0), (99, 1.0),
    (100, 1.0), (150, 1.0),
])
def test_boss_spawn_chance(day, expected):
    assert boss_spawn_chance(day) == pytest.approx(expected)
```

- [ ] **Step 2: 실패 확인**

```bash
python -m pytest tests/test_boss_spawn.py -v
```
Expected: ImportError.

- [ ] **Step 3: `combat.py`에 함수 추가**

```python
def boss_spawn_chance(day: int) -> float:
    """전투당 보스 스폰 확률."""
    if day < 40: return 0.0
    if day < 60: return 0.05
    if day < 80: return 0.10
    if day < 90: return 0.25
    return 1.0
```

- [ ] **Step 4: 통과 확인**

```bash
python -m pytest tests/test_boss_spawn.py -v
```
Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add backend/app/combat.py backend/tests/test_boss_spawn.py && git commit -m "feat(combat): boss_spawn_chance by day bracket

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 3.2: `roll_demon` 보스 분기 (TDD)

**Files:**
- Modify: `backend/app/combat.py`
- Modify: `backend/tests/test_boss_spawn.py`

- [ ] **Step 1: 실패 테스트 — `test_boss_spawn.py`에 추가**

```python
from app.combat import roll_demon


def test_roll_demon_day_under_40_never_boss():
    for seed in range(50):
        d = roll_demon(day=20, defeated_boss_ids=set(), seed=seed)
        assert not d.get("is_boss")


def test_roll_demon_day_100_forces_surt():
    d = roll_demon(day=100, defeated_boss_ids=set(), seed=0)
    assert d.get("is_boss") is True
    assert d.get("boss_id") == "surt"


def test_roll_demon_all_mid_dead_forces_surt():
    all_mid = {"belphegor","beelzebub","mammon","leviathan","asmodeus","satan","lucifer"}
    d = roll_demon(day=60, defeated_boss_ids=all_mid, seed=0)
    assert d.get("boss_id") == "surt"


def test_roll_demon_surt_dead_after_all_returns_regular():
    all_dead = {"belphegor","beelzebub","mammon","leviathan","asmodeus","satan","lucifer","surt"}
    d = roll_demon(day=100, defeated_boss_ids=all_dead, seed=0)
    assert not d.get("is_boss")


def test_roll_demon_boss_picks_weakest_alive():
    # day 90 → 100% chance, defeated={belphegor,beelzebub} → 다음 약한 맘몬
    d = roll_demon(day=90, defeated_boss_ids={"belphegor","beelzebub"}, seed=0)
    assert d.get("boss_id") == "mammon"


def test_roll_demon_day40_eventually_spawns_boss():
    # 5% 확률이라도 50번 굴리면 최소 1번은 떠야 (확률 ≈ 92%)
    spawned = any(
        roll_demon(day=40, defeated_boss_ids=set(), seed=s).get("is_boss")
        for s in range(100)
    )
    assert spawned
```

- [ ] **Step 2: 실패 확인**

```bash
python -m pytest tests/test_boss_spawn.py -v
```
Expected: 새 테스트들은 `roll_demon() got unexpected kwarg 'defeated_boss_ids'`로 실패.

- [ ] **Step 3: `roll_demon` 시그니처·본문 수정**

`backend/app/combat.py`의 `roll_demon`을 다음으로 교체:

```python
from .bosses import MID_BOSSES, FINAL_BOSS, weakest_alive


def roll_demon(day: int = 1, defeated_boss_ids: set[str] | None = None,
               seed: int | None = None) -> dict[str, Any]:
    """day의 난이도 범위와 보스 스폰 규칙을 적용해 적 1마리를 반환.

    defeated_boss_ids가 None이면 빈 집합으로 취급 (테스트 호환).
    """
    rng = random.Random(seed)
    defeated = defeated_boss_ids or set()
    surt_dead = "surt" in defeated
    alive_mid = weakest_alive(defeated)

    def _boss_to_demon(b: dict[str, Any]) -> dict[str, Any]:
        return {"type": b["name"], "attribute": b["attribute"],
                "difficulty": b["difficulty"],
                "is_boss": True, "boss_id": b["boss_id"], "sin": b.get("sin")}

    # day 100+ → 수르트 무조건 (살아있을 때)
    if day >= 100 and not surt_dead:
        return _boss_to_demon(FINAL_BOSS)

    # 모든 mid-boss 처치 → 수르트 조기 등장
    if alive_mid is None and not surt_dead:
        return _boss_to_demon(FINAL_BOSS)

    # 확률적 mid-boss
    if alive_mid is not None and rng.random() < boss_spawn_chance(day):
        return _boss_to_demon(alive_mid)

    # 일반 적 (기존 로직)
    day_lo, day_hi = difficulty_range(day)
    eligible = [d for d in DEMONS
                if d["difficulty"][0] <= day_hi and d["difficulty"][1] >= day_lo]
    pool = eligible or DEMONS
    base = rng.choice(pool)
    d_lo = max(base["difficulty"][0], day_lo)
    d_hi = min(base["difficulty"][1], day_hi)
    if d_lo > d_hi:
        d_lo, d_hi = day_lo, day_hi
    return {"type": base["type"], "attribute": base["attribute"],
            "difficulty": rng.randint(d_lo, d_hi)}
```

- [ ] **Step 4: 통과 + 기존 회귀 확인**

```bash
python -m pytest tests/test_boss_spawn.py tests/test_combat.py -v
```
Expected: 모두 PASS. `test_roll_demon_day_difficulty_range`(day 1–5)는 영향 없어야 함.

- [ ] **Step 5: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add backend/app/combat.py backend/tests/test_boss_spawn.py && git commit -m "feat(combat): roll_demon picks bosses by day chance + weakest-alive order

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase 4 — `run_battle` 통합

### Task 4.1: `repo.list_defeated_boss_ids` 헬퍼

**Files:**
- Modify: `backend/app/repo.py`

- [ ] **Step 1: 함수 추가 — `backend/app/repo.py` 끝 부분에**

```python
def list_defeated_boss_ids(player_id: int) -> set[str]:
    """day_events에서 kind='boss_kill' payload.boss_id 모음."""
    rows = _client().table("day_events").select("payload") \
        .eq("player_id", player_id).eq("kind", "boss_kill").execute().data
    return {r["payload"]["boss_id"] for r in rows if r.get("payload", {}).get("boss_id")}
```

- [ ] **Step 2: 시그니처 확인**

```bash
cd /home/afraidnot/dev/smith-tycoon/backend && source .venv/bin/activate && python -c "
from app import repo
import inspect
print(inspect.signature(repo.list_defeated_boss_ids))
"
```
Expected: `(player_id: int) -> set[str]`

- [ ] **Step 3: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add backend/app/repo.py && git commit -m "feat(repo): list_defeated_boss_ids(player_id) helper

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 4.2: `run_battle` 보스 처치 처리 + return demon

**Files:**
- Modify: `backend/app/combat.py`
- Modify: `backend/tests/test_integration_day.py` (FakeRepo)
- Modify: `backend/tests/test_integration_meta.py` (FakeRepo)

- [ ] **Step 1: `run_battle` 수정**

`backend/app/combat.py`의 `run_battle`을 다음과 같이 변경:

(a) `roll_demon` 호출 시 defeated_boss_ids 전달:
```python
defeated_ids = repo.list_defeated_boss_ids(pid)
demon = roll_demon(day=player["current_day"], defeated_boss_ids=defeated_ids)
```

(b) `delta = apply_outcomes(outcomes)` 직후, update_player 호출 직전에 보스 보너스 반영:
```python
delta = apply_outcomes(outcomes)
if outcomes["demon"] == "killed" and demon.get("is_boss"):
    delta["reputation"] += 10
```

(c) `battle_row` 삽입 직후, day_event 'battle' 기록 후에 boss_kill 이벤트 기록:
```python
if outcomes["demon"] == "killed" and demon.get("is_boss"):
    repo.insert_day_event(
        pid, day=player["current_day"], phase=player["current_phase"],
        kind="boss_kill",
        payload={"boss_id": demon["boss_id"], "boss_name": demon["type"],
                 "sin": demon.get("sin"), "battle_id": battle_row["id"]},
    )
    if demon["boss_id"] == "surt":
        repo.insert_day_event(
            pid, day=player["current_day"], phase=player["current_phase"],
            kind="surt_kill",
            payload={"boss_id": "surt", "boss_name": demon["type"],
                     "battle_id": battle_row["id"], "final": True},
        )
```

(d) return 시 demon 포함:
```python
return {"script": script, "outcomes": outcomes, "demon": demon,
        "next_phase": repo.load_player(pid)["current_phase"]}
```

- [ ] **Step 2: `FakeRepo`에 `list_defeated_boss_ids` 추가**

`backend/tests/test_integration_day.py`의 `FakeRepo` 클래스에:

```python
def list_defeated_boss_ids(self, player_id):
    return {e["payload"]["boss_id"] for e in self.day_events
            if e["kind"] == "boss_kill" and e.get("payload", {}).get("boss_id")}
```

`backend/tests/test_integration_meta.py`의 `FakeRepo`에도 같은 메서드 추가.

- [ ] **Step 3: 전체 pytest 확인**

```bash
python -m pytest -q
```
Expected: 모두 PASS (기존 통합 테스트는 day 1이라 보스 등장 없음).

- [ ] **Step 4: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add backend/app/combat.py backend/tests/test_integration_day.py backend/tests/test_integration_meta.py && git commit -m "feat(combat): run_battle records boss_kill + bonus rep, returns demon

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 4.3: Day 100 수르트 통합 테스트

**Files:**
- Modify: `backend/tests/test_integration_meta.py` (또는 신규)

- [ ] **Step 1: 통합 테스트 추가 — `test_integration_meta.py` 끝에**

```python
@pytest.mark.asyncio
async def test_day_100_surt_appears_and_is_killed():
    """Day 100에서 강력한 무기로 수르트 처치 → boss_kill + surt_kill 이벤트."""
    from app import combat, hero_registry
    from unittest.mock import patch

    fake = FakeRepo()
    fake.player["current_day"] = 100
    fake.player["current_phase"] = "hero1_battle"
    # 충분히 강한 무기
    fake.weapons.append({
        "id": 999, "owner": "sold", "name": "필멸검", "type": "양손검",
        "rarity": 95, "sharpness": 95, "attribute": "물",   # 물→불 (수르트 불) 1.3 보정
        "skill": "...", "str_req": 1, "mag_req": 1,
        "materials_used": [], "enhancement_level": 0, "player_id": 1, "created_day": 1,
    })
    fake.heroes.append({
        "id": 50, "name": "용사", "job": "검사", "str": 99, "mag": 99,
        "gold": 0, "mood": "여유로움", "personality_tags": ["호탕"],
        "affinity": 0, "status": "alive", "return_day": None, "history": [],
        "nickname": None, "held_weapon_id": 999, "visit_count": 1,
    })

    with patch.object(combat, "repo", fake), \
         patch.object(hero_registry, "repo", fake):
        result = await combat.run_battle(fake.player, 50, 999)

    assert result["demon"].get("is_boss") is True
    assert result["demon"].get("boss_id") == "surt"
    # 강력 무기 + 상성 → 대부분 처치 (랜덤이라 약간의 우연 허용은 없음 — 강제값에서는 거의 항상 killed)
    if result["outcomes"]["demon"] == "killed":
        kinds = [e["kind"] for e in fake.day_events]
        assert "boss_kill" in kinds
        assert "surt_kill" in kinds
```

- [ ] **Step 2: 실행**

```bash
python -m pytest tests/test_integration_meta.py::test_day_100_surt_appears_and_is_killed -v
```
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add backend/tests/test_integration_meta.py && git commit -m "test: day 100 surt encounter + kill events

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase 5 — Day summary boss 포맷

### Task 5.1: day_summary boss_kill 카운트 + 포맷

**Files:**
- Modify: `backend/app/day_summary.py`

- [ ] **Step 1: `summarize_events`에 'boss_kill' 카운트 추가**

`summarize_events` 내부의 카운트 로직에 'boss_kill' 케이스를 더해 반환 dict에 `"boss_kills"` 키 포함시킴. 정확한 변경 위치는 함수 구조 따라가되, 다른 kind 카운트와 같은 패턴으로:

```python
def summarize_events(events):
    sales = sum(1 for e in events if e["kind"] == "sale")
    battles = sum(1 for e in events if e["kind"] == "battle")
    forges  = sum(1 for e in events if e["kind"] == "forge")
    boss_kills = sum(1 for e in events if e["kind"] == "boss_kill")
    # ... 기타 기존 카운트
    return {"sales": sales, "battles": battles, "forges": forges,
            "boss_kills": boss_kills, ...}
```

(기존 dict 키 유지하면서 boss_kills만 추가.)

- [ ] **Step 2: 회귀 확인**

```bash
python -m pytest tests/test_day_summary.py -v
```
Expected: 기존 테스트 PASS.

- [ ] **Step 3: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add backend/app/day_summary.py && git commit -m "feat(day_summary): count boss_kills

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase 6 — 프론트엔드

### Task 6.1: Demon 타입 확장 + BattleResponse에 demon 추가

**Files:**
- Modify: `frontend/src/types.ts`

- [ ] **Step 1: types.ts 수정**

기존 `BattleResponse`에 `demon` 필드 추가. `Demon` 타입 신규:

```typescript
export interface Demon {
  type: string;
  attribute: string | null;
  difficulty: number;
  is_boss?: boolean;
  boss_id?: string;
  sin?: string | null;
}

export interface BattleResponse {
  script: string;
  outcomes: { hero: string; weapon: string; demon: string };
  demon: Demon;
  next_phase: string;
}
```

(기존 BattleResponse에 `demon` 누락이면 추가, 이미 있으면 타입을 신규 `Demon`으로 변경.)

- [ ] **Step 2: tsc 확인**

```bash
cd /home/afraidnot/dev/smith-tycoon/frontend && npx tsc --noEmit
```
Expected: exit 0 (다른 컴포넌트는 demon을 안 쓰니 깨지지 않아야 함).

- [ ] **Step 3: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add frontend/src/types.ts && git commit -m "feat(frontend): Demon type + BattleResponse.demon

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 6.2: BattleResult — 보스 강조 표시

**Files:**
- Modify: `frontend/src/components/BattleResult.tsx`

- [ ] **Step 1: 컴포넌트 수정**

현재 본문 시작 부분에 demon 정보 라인 추가. result.demon이 보스면 빨간 강조 + ⚜:

```tsx
return (
  <div>
    <h2>전투 결과</h2>
    {result.demon && (
      <p style={result.demon.is_boss ? { color: "#c00", fontWeight: "bold" } : undefined}>
        {result.demon.is_boss ? "⚜ " : ""}
        상대: {result.demon.type}
        {result.demon.sin && <small> ({result.demon.sin})</small>}
        {result.demon.attribute && <small> · {result.demon.attribute}</small>}
        <small> · 난이도 {result.demon.difficulty}</small>
      </p>
    )}
    <p style={{ whiteSpace: "pre-wrap" }}>{result.script}</p>
    <ul>
      <li>용사: <strong>{result.outcomes.hero}</strong></li>
      <li>무기: <strong>{result.outcomes.weapon}</strong></li>
      <li>마왕군: <strong>{result.outcomes.demon}</strong></li>
    </ul>
    <button className="btn" onClick={onDone}>다음으로</button>
  </div>
);
```

- [ ] **Step 2: tsc 확인**

```bash
npx tsc --noEmit
```
Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add frontend/src/components/BattleResult.tsx && git commit -m "feat(frontend): highlight boss in BattleResult

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 6.3: DaySummary boss_kill 한글 포맷

**Files:**
- Modify: `frontend/src/components/DaySummary.tsx`

- [ ] **Step 1: `formatEvent`에 boss_kill 케이스 추가**

기존 switch 문에 case 추가:

```tsx
case "boss_kill": {
  const p = e.payload as { boss_name?: string; sin?: string };
  return `⚜ 보스 처치: ${p.boss_name}${p.sin ? ` (${p.sin})` : ""}`;
}
case "surt_kill": {
  const p = e.payload as { boss_name?: string };
  return `🔥 최종보스 ${p.boss_name} 처치! 게임 승리.`;
}
```

- [ ] **Step 2: tsc 확인**

```bash
npx tsc --noEmit
```
Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add frontend/src/components/DaySummary.tsx && git commit -m "feat(frontend): DaySummary formats boss_kill / surt_kill

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Phase 7 — 최종 검증

### Task 7.1: 전체 테스트 + 라이브 smoke

- [ ] **Step 1: 백엔드 풀 테스트**

```bash
cd /home/afraidnot/dev/smith-tycoon/backend && source .venv/bin/activate && python -m pytest -q
```
Expected: 모두 PASS (기존 89 + 신규 ≈ 30+ = 120+).

- [ ] **Step 2: 프론트엔드 tsc**

```bash
cd /home/afraidnot/dev/smith-tycoon/frontend && npx tsc --noEmit
```
Expected: exit 0.

- [ ] **Step 3: 라이브 smoke (선택적)**

`/state` 직접 day=100으로 만져 보스 등장 확인. SQL로 player.current_day=100 강제 후 hero1_battle phase에서 `POST /battle` 호출 → 응답 `demon.is_boss=true, boss_id=surt`.

```bash
# 백엔드 띄운 상태에서
curl -s -X POST -H "X-Player-Nickname: TEST" http://127.0.0.1:8000/game/reset
# Supabase MCP로 직접 player.current_day=100, current_phase='hero1_battle' 설정 후
curl -s -X POST -H "X-Player-Nickname: TEST" http://127.0.0.1:8000/battle | head -c 500
```

- [ ] **Step 4: 최종 폴리시 커밋 (있으면)**

```bash
cd /home/afraidnot/dev/smith-tycoon && git status
# 변경 있으면 commit
```

---

## Self-review 메모

- 스펙 §2 보스 정의 — Task 1.1로 커버.
- 스펙 §3 등장 확률·선택 — Task 3.1, 3.2로 커버.
- 스펙 §4 5행 상성 — Task 2.1, 2.2로 커버.
- 스펙 §5 보스 처치 효과 — Task 4.1, 4.2로 커버. surt_kill 이벤트 4.2에 포함.
- 스펙 §6 파일 구조 — 위 Task 매핑과 일치.
- 스펙 §7 테스트 — Task 1.1, 2.1, 2.2, 3.1, 3.2, 4.3에 분산.
- 스펙 §8 범위 외 (엔딩 UI / 전설 등재 / 보스 전리품 / LLM 톤) — 본 플랜에서 의도적 미포함.

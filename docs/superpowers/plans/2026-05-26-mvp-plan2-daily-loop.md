# MVP Plan 2 — Daily Loop & Merchant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Plan 1의 vertical slice 위에 5일 운영 루프 + 상인 협상 + 일일 요약 + 전투 강화 + Supabase RLS 정책을 얹어 architecture.md §6의 일일 플로우가 5일간 돌아가는 MVP를 완성.

**Architecture:** state_machine을 10+1개 phase × 5일 구조로 확장. 상인 모듈과 hero_registry 모듈 신설. 모든 LLM 호출은 기존 게이트웨이 재사용. Server-authoritative 원칙·repo 단일 의존성 원칙·LLM 응답 신뢰 안 함 원칙 모두 Plan 1과 동일하게 유지.

**Tech Stack:** Python 3.12 + FastAPI + supabase-py + httpx + pytest + Jinja2 / React + Vite + TypeScript / Supabase (Postgres) / OpenAI 호환 LLM API.

**선행:** Plan 2 spec — `docs/superpowers/specs/2026-05-26-mvp-plan2-design.md`. Plan 1은 이미 main에 머지됨.

---

## File Structure

### Backend

```
backend/
├── migrations/
│   ├── 001_initial.sql                (기존)
│   └── 002_daily_loop.sql             신규 — 신규 테이블 + RLS + heroes.held_weapon_id
├── app/
│   ├── state_machine.py               변경 — PHASES 확장 + advance_to_next_day
│   ├── repo.py                        변경 — 신규 테이블 CRUD + return_day 조회
│   ├── forge.py                       변경 없음 (phase 이름만 API에서 처리)
│   ├── negotiation.py                 변경 — step_buy, finalize_buy 추가
│   ├── combat.py                      변경 — roll_demon(day=N), prompt 변수
│   ├── merchant.py                    신규 — generate_today
│   ├── hero_registry.py               신규 — heroes_for_today, schedule_return
│   ├── day_summary.py                 신규 — build(day)
│   ├── llm/prompts/
│   │   ├── battle.j2                  변경 — 판정 지침 추가
│   │   └── negotiate_buy.j2           신규
│   └── api/
│       ├── state.py                   변경 — merchant·day 컨텍스트 포함
│       ├── forge.py                   변경 — forge_open / forge_open_2 모두 허용 + /forge/skip
│       ├── negotiate.py               변경 — hero1/2/3 협상 phase 허용
│       ├── battle.py                  변경 — hero1/2/3 전투 phase 허용
│       ├── merchant.py                신규
│       ├── day.py                     신규
│       └── game.py                    변경 — hero 생성을 hero_registry로 위임
└── tests/
    ├── test_state_machine.py          변경
    ├── test_combat.py                 변경
    ├── test_negotiation.py            변경 — step_buy 추가
    ├── test_merchant.py               신규
    ├── test_hero_registry.py          신규
    ├── test_day_summary.py            신규
    ├── test_integration_day.py        신규 — 하루 골든 패스
    └── fixtures/llm/
        ├── negotiate_buy_accept.json  신규
        ├── negotiate_buy_counter.json 신규
        └── negotiate_buy_reject.json  신규
```

### Frontend

```
frontend/src/
├── types.ts                           변경 — Merchant/DaySummary 타입
├── api.ts                             변경 — merchant·day 엔드포인트
└── components/
    ├── DayRouter.tsx                  변경 — 신규 phase 라우팅
    ├── SidePanel.tsx                  변경 — day 표시
    ├── ForgePanel.tsx                 변경 — skip 버튼
    ├── MerchantPanel.tsx              신규
    ├── MerchantNegotiation.tsx        신규
    ├── DaySummary.tsx                 신규
    └── GameOver.tsx                   신규
```

### Docs

```
docs/superpowers/plans/
├── 2026-05-26-mvp-plan2-daily-loop.md     (이 문서)
└── 2026-05-26-mvp-plan2-checklist.md      신규 — 수동 검증
```

---

## Task 1: 마이그레이션 002 — 신규 테이블 + heroes 확장 + RLS

**Files:**
- Create: `backend/migrations/002_daily_loop.sql`

- [ ] **Step 1: 마이그레이션 파일 작성**

```sql
-- 002_daily_loop.sql — Plan 2: 다일 루프·상인·일일 요약·RLS

create table if not exists merchants_today (
  id bigserial primary key,
  player_id bigint references players(id) on delete cascade,
  day int not null,
  materials jsonb not null,
  weapon jsonb,
  outcome text not null default 'pending' check (outcome in ('pending','done')),
  unique (player_id, day)
);

create table if not exists day_events (
  id bigserial primary key,
  player_id bigint references players(id) on delete cascade,
  day int not null,
  phase text not null,
  kind text not null,
  payload jsonb not null,
  created_at timestamptz not null default now()
);

alter table heroes add column if not exists held_weapon_id bigint references weapons(id);

-- RLS
alter table players          enable row level security;
alter table inventory        enable row level security;
alter table weapons          enable row level security;
alter table heroes           enable row level security;
alter table negotiations     enable row level security;
alter table battles          enable row level security;
alter table merchants_today  enable row level security;
alter table day_events       enable row level security;
alter table materials        enable row level security;

drop policy if exists "materials_anon_read" on materials;
create policy "materials_anon_read"
  on materials for select to anon using (true);
```

- [ ] **Step 2: Supabase에 적용**

수동 단계: 사용자가 Supabase SQL Editor에서 실행하거나, MCP `apply_migration` 사용. 이 task의 구현자는 **파일만 작성·커밋**. 적용은 user / 별도 단계.

- [ ] **Step 3: 검증 — 7 + 2 = 9 테이블 + 1 정책**

`grep -c "create table" backend/migrations/002_daily_loop.sql` → `2`
`grep -c "enable row level security" backend/migrations/002_daily_loop.sql` → `9`
`grep -c "create policy" backend/migrations/002_daily_loop.sql` → `1`

- [ ] **Step 4: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add backend/migrations/002_daily_loop.sql && git commit -m "feat(db): Plan 2 migration — merchants_today, day_events, RLS"
```

---

## Task 2: state_machine 확장

**Files:**
- Modify: `backend/app/state_machine.py`
- Modify: `backend/tests/test_state_machine.py`

- [ ] **Step 1: 테스트 갱신 — `backend/tests/test_state_machine.py` 전체 교체**

```python
import pytest
from app.state_machine import (
    next_phase, assert_phase, advance_to_next_day,
    INITIAL_PHASE, PHASES, PhaseError,
)


def test_initial_phase_is_forge_open():
    assert INITIAL_PHASE == "forge_open"


def test_phase_sequence():
    expected = [
        "forge_open", "hero1_negotiate", "hero1_battle",
        "merchant_negotiate",
        "hero2_negotiate", "hero2_battle",
        "forge_open_2",
        "hero3_negotiate", "hero3_battle",
        "day_summary",
    ]
    for i in range(len(expected) - 1):
        assert next_phase(expected[i]) == expected[i + 1]


def test_day_summary_next_goes_back_to_forge_open_marker():
    # day_summary의 다음은 sentinel "next_day" 반환 — 실제 day 전환은 advance_to_next_day가 처리
    assert next_phase("day_summary") == "next_day"


def test_game_over_has_no_next():
    with pytest.raises(PhaseError):
        next_phase("game_over")


def test_assert_phase_match_and_mismatch():
    assert_phase("forge_open", "forge_open")
    with pytest.raises(PhaseError):
        assert_phase("hero1_negotiate", "forge_open")


def test_advance_to_next_day_increments_day_and_resets_phase():
    p = {"current_day": 1, "current_phase": "day_summary"}
    advance_to_next_day(p)
    assert p == {"current_day": 2, "current_phase": "forge_open"}


def test_advance_to_next_day_at_day_5_goes_to_game_over():
    p = {"current_day": 5, "current_phase": "day_summary"}
    advance_to_next_day(p)
    assert p == {"current_day": 5, "current_phase": "game_over"}
```

- [ ] **Step 2: 테스트 실행 (FAIL 확인)**

```bash
cd /home/afraidnot/dev/smith-tycoon/backend && ./.venv/bin/pytest tests/test_state_machine.py -v
```
Expected: import 또는 attribute 에러.

- [ ] **Step 3: `backend/app/state_machine.py` 전체 교체**

```python
class PhaseError(Exception):
    pass


PHASES = [
    "forge_open",
    "hero1_negotiate",
    "hero1_battle",
    "merchant_negotiate",
    "hero2_negotiate",
    "hero2_battle",
    "forge_open_2",
    "hero3_negotiate",
    "hero3_battle",
    "day_summary",
]
INITIAL_PHASE = PHASES[0]
MAX_DAY = 5


def next_phase(current: str) -> str:
    if current == "day_summary":
        return "next_day"   # sentinel — advance_to_next_day가 실제 처리
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


def advance_to_next_day(player: dict) -> None:
    """player dict in-place 갱신. day=5에서 호출되면 game_over."""
    if player["current_day"] >= MAX_DAY:
        player["current_phase"] = "game_over"
    else:
        player["current_day"] += 1
        player["current_phase"] = "forge_open"
```

- [ ] **Step 4: 테스트 PASS 확인**

```bash
cd /home/afraidnot/dev/smith-tycoon/backend && ./.venv/bin/pytest tests/test_state_machine.py -v
```
Expected: 7 PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add backend/app/state_machine.py backend/tests/test_state_machine.py && git commit -m "feat(state_machine): 10-phase daily loop with advance_to_next_day"
```

---

## Task 3: repo 확장 — 신규 테이블 CRUD + hero 조회

**Files:**
- Modify: `backend/app/repo.py`

- [ ] **Step 1: `backend/app/repo.py` 끝에 함수 추가**

```python


# --- Plan 2: merchants_today ---

def get_merchant_today(day: int) -> dict[str, Any] | None:
    c = _client()
    rows = c.table("merchants_today").select("*") \
        .eq("player_id", PLAYER_ID).eq("day", day).limit(1).execute().data
    return rows[0] if rows else None


def insert_merchant_today(m: dict[str, Any]) -> dict[str, Any]:
    return _client().table("merchants_today").insert({**m, "player_id": PLAYER_ID}).execute().data[0]


def update_merchant_today(merchant_id: int, **fields: Any) -> None:
    _client().table("merchants_today").update(fields).eq("id", merchant_id).execute()


def add_inventory(material_id: int, qty: int) -> None:
    """인벤토리에 재료 추가. 없으면 insert, 있으면 qty 증가."""
    c = _client()
    rows = c.table("inventory").select("qty") \
        .eq("player_id", PLAYER_ID).eq("material_id", material_id).limit(1).execute().data
    if rows:
        c.table("inventory").update({"qty": rows[0]["qty"] + qty}) \
            .eq("player_id", PLAYER_ID).eq("material_id", material_id).execute()
    else:
        c.table("inventory").insert(
            {"player_id": PLAYER_ID, "material_id": material_id, "qty": qty}
        ).execute()


# --- Plan 2: day_events ---

def insert_day_event(day: int, phase: str, kind: str, payload: dict[str, Any]) -> None:
    _client().table("day_events").insert({
        "player_id": PLAYER_ID, "day": day, "phase": phase,
        "kind": kind, "payload": payload,
    }).execute()


def list_day_events(day: int) -> list[dict[str, Any]]:
    return _client().table("day_events").select("*") \
        .eq("player_id", PLAYER_ID).eq("day", day).order("created_at").execute().data


# --- Plan 2: hero 조회 확장 ---

def list_alive_heroes_ready(day: int) -> list[dict[str, Any]]:
    """alive 상태이며 (return_day is null or return_day <= day) 인 용사들."""
    c = _client()
    # supabase-py는 .or_() 문법 사용
    return c.table("heroes").select("*").eq("status", "alive") \
        .or_(f"return_day.is.null,return_day.lte.{day}").execute().data
```

- [ ] **Step 2: 파싱 확인**

```bash
cd /home/afraidnot/dev/smith-tycoon/backend && ./.venv/bin/python -c "from app import repo; print('ok')"
```
Expected: `ok`

- [ ] **Step 3: 기존 테스트 회귀 확인**

```bash
cd /home/afraidnot/dev/smith-tycoon/backend && ./.venv/bin/pytest -v
```
Expected: 모든 기존 테스트 PASS.

- [ ] **Step 4: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add backend/app/repo.py && git commit -m "feat(repo): merchants_today, day_events, hero ready query"
```

---

## Task 4: combat — day 기반 난이도 + 프롬프트 강화

**Files:**
- Modify: `backend/app/combat.py`
- Modify: `backend/app/llm/prompts/battle.j2`
- Modify: `backend/tests/test_combat.py`

- [ ] **Step 1: 테스트 갱신 — `backend/tests/test_combat.py` 전체 교체**

```python
import pytest
from app.combat import apply_outcomes, roll_demon


def test_apply_outcomes_survived_killed_increases_rep():
    delta = apply_outcomes({"hero": "survived", "weapon": "preserved", "demon": "killed"})
    assert delta["reputation"] >= 2


def test_apply_outcomes_died_destroyed_decreases_rep():
    delta = apply_outcomes({"hero": "died", "weapon": "destroyed", "demon": "survived"})
    assert delta["reputation"] < 0


def test_apply_outcomes_neutral_outcomes_no_change():
    delta = apply_outcomes({"hero": "injured", "weapon": "preserved", "demon": "survived"})
    assert delta["reputation"] == 0


@pytest.mark.parametrize("day,lo,hi", [(1, 1, 10), (2, 3, 15), (3, 8, 22), (4, 14, 30), (5, 20, 40)])
def test_roll_demon_day_difficulty_range(day, lo, hi):
    for seed in range(30):
        d = roll_demon(day=day, seed=seed)
        assert lo <= d["difficulty"] <= hi, f"day={day} seed={seed} got {d['difficulty']}"
```

- [ ] **Step 2: 테스트 실행 (parametrize FAIL 확인)**

```bash
cd /home/afraidnot/dev/smith-tycoon/backend && ./.venv/bin/pytest tests/test_combat.py -v
```
Expected: roll_demon 관련 5개 FAIL.

- [ ] **Step 3: `backend/app/combat.py` 갱신**

```python
from __future__ import annotations
import random
from typing import Any
from . import repo, state_machine
from .llm.client import complete_json

DEMONS = [
    {"type": "고블린",   "attribute": "흙"},
    {"type": "지옥개",   "attribute": "불"},
    {"type": "작은 영혼","attribute": "물"},
    {"type": "임프",     "attribute": "불"},
]

# day → (난이도 lo, 난이도 hi)
DIFFICULTY_BY_DAY = {1: (1, 10), 2: (3, 15), 3: (8, 22), 4: (14, 30), 5: (20, 40)}


def roll_demon(day: int = 1, seed: int | None = None) -> dict[str, Any]:
    rng = random.Random(seed)
    lo, hi = DIFFICULTY_BY_DAY.get(day, (1, 10))
    base = rng.choice(DEMONS)
    return {"type": base["type"], "attribute": base["attribute"],
            "difficulty": rng.randint(lo, hi)}


def apply_outcomes(outcomes: dict[str, str]) -> dict[str, int]:
    rep = 0
    if outcomes["hero"] == "survived":
        rep += 1
    elif outcomes["hero"] == "died":
        rep -= 2
    if outcomes["weapon"] == "destroyed":
        rep -= 1
    if outcomes["demon"] == "killed":
        rep += 1
    return {"reputation": rep}


async def run_battle(hero_id: int, weapon_id: int | None) -> dict[str, Any]:
    hero = repo.get_hero(hero_id)
    weapon = repo.get_weapon(weapon_id) if weapon_id else None
    player = repo.load_player()
    demon = roll_demon(day=player["current_day"])

    llm = await complete_json("battle", "battle_basic",
                              hero=hero, weapon=weapon, demon=demon)
    outcomes = llm["outcomes"]
    delta = apply_outcomes(outcomes)

    repo.update_player(reputation=player["reputation"] + delta["reputation"],
                       current_phase=state_machine.next_phase(player["current_phase"]))

    if outcomes["hero"] == "died":
        repo.update_hero(hero_id, status="dead")

    battle_row = repo.insert_battle({
        "day": player["current_day"],
        "hero_id": hero_id,
        "weapon_id": weapon_id,
        "demon": demon,
        "script_text": llm["script"],
        "outcomes": outcomes,
    })

    repo.insert_day_event(
        day=player["current_day"],
        phase=player["current_phase"],
        kind="battle",
        payload={"battle_id": battle_row["id"], "outcomes": outcomes,
                 "hero_id": hero_id, "demon": demon, "rep_delta": delta["reputation"]},
    )

    return {"script": llm["script"], "outcomes": outcomes,
            "next_phase": repo.load_player()["current_phase"]}
```

- [ ] **Step 4: `backend/app/llm/prompts/battle.j2` 전체 교체**

```
당신은 판타지 세계의 전투 뉴스 기자입니다. 다음 정보로 전투 결과를 뉴스 한 단락(3~5문장)으로 묘사하고 결과 코드를 정해주세요.

용사: {{ hero.name }} ({{ hero.job }}, 근력 {{ hero.str }}, 마력 {{ hero.mag }})
무기: {% if weapon %}{{ weapon.name }} (예리도 {{ weapon.sharpness }}, 희귀도 {{ weapon.rarity }}){% else %}없음(맨손){% endif %}
적: {{ demon.type }} (난이도 {{ demon.difficulty }})

전투 판정 지침 — 반드시 따를 것:
- 용사 전투력 ≈ (근력 + 마력) + (무기 예리도 / 2 if 무기 있음 else 0)
- 적 위협력 = 난이도
- 전투력 ≥ 위협력 × 1.5 → 거의 항상 hero=survived + demon=killed, 무기=preserved
- 전투력 ≈ 위협력 → hero가 survived 또는 injured 혼합, demon은 killed 또는 fled
- 전투력 < 위협력 × 0.7 → hero가 injured 또는 died, demon이 survived 자주 발생
- 무기 없으면 (맨손): hero 부상·사망 확률 +30%, demon survived 확률 ↑
- 무기 예리도 < 30이면 weapon=destroyed 확률 ↑, ≥ 60이면 거의 preserved
- 결과 코드는 위 기준을 일관되게 따르고, script는 그 결과를 자연스럽게 묘사

다음 JSON 형식으로만 답하세요:
{"script": "<뉴스 단락>", "outcomes": {"hero": "survived"|"injured"|"died", "weapon": "preserved"|"destroyed"|"none", "demon": "killed"|"fled"|"survived"}}
```

- [ ] **Step 5: 테스트 PASS 확인**

```bash
cd /home/afraidnot/dev/smith-tycoon/backend && ./.venv/bin/pytest tests/test_combat.py -v
```
Expected: 8 PASS (3 outcomes + 5 parametrized).

- [ ] **Step 6: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add backend/app/combat.py backend/app/llm/prompts/battle.j2 backend/tests/test_combat.py && git commit -m "feat(combat): day-scaled difficulty and stat-aware battle prompt"
```

---

## Task 5: hero_registry 모듈

**Files:**
- Create: `backend/app/hero_registry.py`
- Create: `backend/tests/test_hero_registry.py`

- [ ] **Step 1: 테스트 작성 (FAIL 먼저)**

`backend/tests/test_hero_registry.py`:

```python
from app.hero_registry import generate_hero, schedule_return


def test_generate_hero_has_required_fields():
    h = generate_hero(seed=1)
    assert "name" in h and "job" in h
    assert h["str"] >= 5 and h["str"] <= 15
    assert h["mag"] >= 2 and h["mag"] <= 12
    assert h["status"] == "alive"
    assert 1 <= int(h["name"]) <= 1000


def test_schedule_return_survived():
    fields = schedule_return("survived", current_day=2)
    assert fields == {"status": "alive", "return_day": 5}


def test_schedule_return_fled():
    fields = schedule_return("fled", current_day=2)
    assert fields == {"status": "fled", "return_day": 9}


def test_schedule_return_died():
    fields = schedule_return("died", current_day=2)
    assert fields == {"status": "dead", "return_day": None}
```

- [ ] **Step 2: 테스트 실행 (FAIL)**

```bash
cd /home/afraidnot/dev/smith-tycoon/backend && ./.venv/bin/pytest tests/test_hero_registry.py -v
```
Expected: ModuleNotFoundError.

- [ ] **Step 3: `backend/app/hero_registry.py` 작성**

```python
from __future__ import annotations
import random
from typing import Any
from . import repo


JOBS = ["검사", "법사", "궁수", "성문 문지기", "거렁뱅이", "청소년", "군인"]
MOODS = ["여유로움", "초조함", "들떠있음", "지친 듯"]
TRAITS = ["호탕", "깐깐", "소심", "허세", "검소"]


def generate_hero(seed: int | None = None) -> dict[str, Any]:
    rng = random.Random(seed)
    return {
        "name": str(rng.randint(1, 1000)),
        "job": rng.choice(JOBS),
        "str": rng.randint(5, 15),
        "mag": rng.randint(2, 12),
        "gold": rng.randint(500, 2000),
        "mood": rng.choice(MOODS),
        "personality_tags": rng.sample(TRAITS, k=2),
        "affinity": 0,
        "status": "alive",
        "history": [],
    }


def heroes_for_today(day: int, count: int = 3) -> list[dict[str, Any]]:
    """오늘 등장할 용사 목록 — 재방문 대상 우선, 부족분 신규 생성·삽입."""
    ready = repo.list_alive_heroes_ready(day)
    # 재방문 우선 — return_day가 가장 작은 순 (오래 기다린 순)
    ready.sort(key=lambda h: (h.get("return_day") or 0))
    picked = ready[:count]
    for _ in range(count - len(picked)):
        h = repo.insert_hero(generate_hero())
        picked.append(h)
    return picked


def schedule_return(battle_outcome: str, current_day: int) -> dict[str, Any]:
    """전투 결과별 다음 등장 일정 + 상태 필드 반환."""
    if battle_outcome == "survived":
        return {"status": "alive", "return_day": current_day + 3}
    if battle_outcome == "fled":
        return {"status": "fled", "return_day": current_day + 7}
    if battle_outcome == "died":
        return {"status": "dead", "return_day": None}
    raise ValueError(f"unknown battle outcome: {battle_outcome}")
```

- [ ] **Step 4: 테스트 PASS**

```bash
cd /home/afraidnot/dev/smith-tycoon/backend && ./.venv/bin/pytest tests/test_hero_registry.py -v
```
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add backend/app/hero_registry.py backend/tests/test_hero_registry.py && git commit -m "feat(hero_registry): generation + return scheduling"
```

---

## Task 6: combat에 schedule_return 통합

**Files:**
- Modify: `backend/app/combat.py`

- [ ] **Step 1: combat.run_battle 안의 hero 갱신 로직 교체**

기존:
```python
if outcomes["hero"] == "died":
    repo.update_hero(hero_id, status="dead")
```

교체:
```python
from . import hero_registry  # 파일 상단으로 옮기되 명시: 기존 import 옆에 추가

...

# 전투 결과별로 status·return_day 갱신
fields = hero_registry.schedule_return(outcomes["hero"], current_day=player["current_day"])
repo.update_hero(hero_id, **fields)
```

상단 import 정리 — `backend/app/combat.py` 상단 import 영역에 `hero_registry` 추가:

```python
from __future__ import annotations
import random
from typing import Any
from . import repo, state_machine, hero_registry
from .llm.client import complete_json
```

- [ ] **Step 2: 전체 백엔드 테스트 회귀 확인**

```bash
cd /home/afraidnot/dev/smith-tycoon/backend && ./.venv/bin/pytest -v
```
Expected: 모든 테스트 PASS.

- [ ] **Step 3: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add backend/app/combat.py && git commit -m "feat(combat): wire hero_registry.schedule_return on battle end"
```

---

## Task 7: merchant 모듈

**Files:**
- Create: `backend/app/merchant.py`
- Create: `backend/tests/test_merchant.py`
- Create: `backend/app/llm/prompts/negotiate_buy.j2`
- Create: `backend/tests/fixtures/llm/negotiate_buy_accept.json`
- Create: `backend/tests/fixtures/llm/negotiate_buy_counter.json`
- Create: `backend/tests/fixtures/llm/negotiate_buy_reject.json`

- [ ] **Step 1: 픽스처 3개 작성**

`backend/tests/fixtures/llm/negotiate_buy_accept.json`:
```json
{"decision": "accept", "message": "좋소, 그 가격에 드리지요.", "counter_price": null}
```

`backend/tests/fixtures/llm/negotiate_buy_counter.json`:
```json
{"decision": "counter", "message": "너무 싸오. 1500은 받아야겠소.", "counter_price": 1500}
```

`backend/tests/fixtures/llm/negotiate_buy_reject.json`:
```json
{"decision": "reject", "message": "그 가격으론 못 팔겠소.", "counter_price": null}
```

- [ ] **Step 2: 프롬프트 작성 — `backend/app/llm/prompts/negotiate_buy.j2`**

```
당신은 떠돌이 상인입니다. 대장장이가 당신의 묶음 상품을 사려고 합니다.

상품 묶음:
{% for m in materials %}- {{ m.name }} × {{ m.qty }} (시세 {{ m.base_price * m.qty }} 골드)
{% endfor %}{% if weapon %}- 무기: {{ weapon.name }} (예리도 {{ weapon.sharpness }}, 희귀도 {{ weapon.rarity }}, 시세 {{ weapon.asking_price }} 골드)
{% endif %}
- 묶음 시세 합계: {{ market_price }} 골드
- 상인이 처음 부른 가격: {{ asking_price }} 골드

지금까지의 대화 (총 {{ prior_rounds|length // 2 }}라운드):
{% for r in prior_rounds %}
- {{ r.role }}: "{{ r.message }}"{% if r.price %} (가격: {{ r.price }}){% endif %}
{% endfor %}

대장장이의 새 제안: "{{ player_message }}" (가격: {{ price_offered }} 골드)

협상 지침:
- 2~4라운드 흥정 후 결론. 첫 라운드에 reject 금지.
- 시세보다 너무 깎으면 counter로 적정선 제안.
- 시세 ±10% 이내면 accept 고려.
- accept 시 counter_price는 null.
- message는 상인 톤(거칠고 빠릿빠릿)으로 한 문장 이상.

다음 JSON 형식으로만 답하세요:
{"decision": "accept" | "reject" | "counter", "counter_price": <정수, counter일 때만>, "message": "<상인 대사>"}
```

- [ ] **Step 3: 테스트 작성 — `backend/tests/test_merchant.py`**

```python
from app.merchant import generate_today, bundle_market_price


def test_bundle_market_price_materials_only():
    bundle = {
        "materials": [
            {"material_id": 1, "qty": 2, "name": "x", "category": "일반", "base_price": 50},
            {"material_id": 2, "qty": 1, "name": "y", "category": "특수", "base_price": 800},
        ],
        "weapon": None,
    }
    assert bundle_market_price(bundle) == 50 * 2 + 800 * 1


def test_bundle_market_price_with_weapon():
    bundle = {
        "materials": [{"material_id": 1, "qty": 1, "name": "x", "category": "일반", "base_price": 50}],
        "weapon": {"asking_price": 500},
    }
    assert bundle_market_price(bundle) == 50 + 500


def test_generate_today_deterministic_with_seed():
    a = generate_today(day=1, seed=42)
    b = generate_today(day=1, seed=42)
    assert a == b


def test_generate_today_has_4_to_6_materials():
    for seed in range(10):
        bundle = generate_today(day=1, seed=seed)
        assert 4 <= len(bundle["materials"]) <= 6
```

- [ ] **Step 4: 테스트 실행 (FAIL)**

```bash
cd /home/afraidnot/dev/smith-tycoon/backend && ./.venv/bin/pytest tests/test_merchant.py -v
```
Expected: ModuleNotFoundError.

- [ ] **Step 5: `backend/app/merchant.py` 작성**

```python
from __future__ import annotations
import json
import random
from pathlib import Path
from typing import Any

_MATERIALS_CATALOG: list[dict[str, Any]] | None = None


def _materials_catalog() -> list[dict[str, Any]]:
    global _MATERIALS_CATALOG
    if _MATERIALS_CATALOG is None:
        path = Path(__file__).parent.parent / "seed" / "materials.json"
        _MATERIALS_CATALOG = json.loads(path.read_text())
    return _MATERIALS_CATALOG


WEAPON_TYPES = ["한손검", "양손검", "한손둔기", "양손둔기", "마법지팡이", "방패", "단도", "표창", "총"]


def generate_today(day: int, seed: int | None = None) -> dict[str, Any]:
    """day별 상인 인벤토리 — materials 4~6종 + weapon 1개."""
    rng = random.Random(seed if seed is not None else f"merchant-{day}")
    catalog = _materials_catalog()

    n_materials = rng.randint(4, 6)
    chosen = rng.sample(catalog, k=min(n_materials, len(catalog)))
    materials = []
    for m in chosen:
        qty = rng.randint(1, 3)
        markup = 1.0 + rng.random() * 0.5
        materials.append({
            "material_id": m["id"], "name": m["name"], "category": m["category"],
            "attribute": m.get("attribute"), "base_price": m["base_price"],
            "qty": qty,
            "asking_price": int(m["base_price"] * qty * markup),
        })

    # 무기 — 예리도 30, 희귀도 30 고정 (architecture.md §5.2)
    wt = rng.choice(WEAPON_TYPES)
    weapon = {
        "name": f"{wt} (상인 매물)",
        "type": wt,
        "rarity": 30,
        "sharpness": 30,
        "attribute": None,
        "skill": "표준품의 안정적인 효과를 가집니다.",
        "str_req": 5,
        "mag_req": 3,
        "asking_price": int(300 * (1.0 + rng.random() * 0.5)),
    }
    return {"materials": materials, "weapon": weapon}


def bundle_market_price(bundle: dict[str, Any]) -> int:
    total = sum(m["base_price"] * m.get("qty", 1) for m in bundle["materials"])
    if bundle.get("weapon"):
        total += bundle["weapon"]["asking_price"]
    return max(10, total)
```

- [ ] **Step 6: 테스트 PASS**

```bash
cd /home/afraidnot/dev/smith-tycoon/backend && ./.venv/bin/pytest tests/test_merchant.py -v
```
Expected: 4 PASS.

- [ ] **Step 7: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add backend/app/merchant.py backend/app/llm/prompts/negotiate_buy.j2 backend/tests/test_merchant.py backend/tests/fixtures/llm/negotiate_buy_*.json && git commit -m "feat(merchant): generate_today + buy negotiation prompt and fixtures"
```

---

## Task 8: negotiation — step_buy / finalize_buy 추가

**Files:**
- Modify: `backend/app/negotiation.py`
- Modify: `backend/tests/test_negotiation.py`

- [ ] **Step 1: 테스트 추가 — `backend/tests/test_negotiation.py` 끝에 append**

```python


def test_clamp_buy_price_lower():
    from app.negotiation import clamp_price
    assert clamp_price(10, base=1000) == 100


def test_market_price_buy_bundle_equivalence():
    """매수와 매도 시세 산정은 별 함수. buy는 merchant.bundle_market_price."""
    from app.merchant import bundle_market_price
    bundle = {"materials": [{"base_price": 100, "qty": 3}], "weapon": None}
    assert bundle_market_price(bundle) == 300
```

- [ ] **Step 2: `backend/app/negotiation.py` 끝에 함수 추가**

```python


# --- Plan 2: 상인 협상 (매수) ---

async def step_buy(merchant_id: int, price_offered: int, player_message: str,
                   neg_id: int | None) -> dict[str, Any]:
    from . import merchant as merchant_module

    m_row = _client_or_repo_get_merchant(merchant_id)
    bundle = {"materials": m_row["materials"], "weapon": m_row.get("weapon")}
    base = merchant_module.bundle_market_price(bundle)
    safe_price = clamp_price(price_offered, base)

    if neg_id is None:
        player = repo.load_player()
        neg = repo.insert_negotiation({
            "day": player["current_day"], "phase": player["current_phase"],
            "kind": "buy", "counterparty_id": merchant_id, "weapon_id": None,
            "materials": bundle, "rounds": [], "outcome": "open",
        })
        neg_id = neg["id"]
        prior_rounds: list[dict[str, Any]] = []
    else:
        neg = repo.get_negotiation(neg_id)
        prior_rounds = neg["rounds"]

    llm = await complete_json(
        "negotiate_buy", "negotiate_buy_accept",
        materials=bundle["materials"], weapon=bundle.get("weapon"),
        market_price=base, asking_price=base,  # 상인 초기 호가는 시세 그대로
        prior_rounds=prior_rounds,
        player_message=player_message,
        price_offered=safe_price,
    )

    decision = llm["decision"]
    counter = llm.get("counter_price")
    if counter is not None:
        counter = clamp_price(int(counter), base)

    new_rounds = prior_rounds + [
        {"role": "player", "message": player_message, "price": safe_price},
        {"role": "merchant", "message": llm["message"], "price": counter},
    ]
    update: dict[str, Any] = {"rounds": new_rounds}
    if decision == "accept":
        update["outcome"] = "accepted"
        update["agreed_price"] = safe_price
    elif decision == "reject":
        update["outcome"] = "rejected"
    repo.update_negotiation(neg_id, **update)

    return {
        "negotiation_id": neg_id,
        "decision": decision,
        "counter_price": counter,
        "message": llm["message"],
    }


def finalize_buy(neg_id: int) -> None:
    neg = repo.get_negotiation(neg_id)
    if neg["outcome"] != "accepted":
        raise ValueError("negotiation not accepted")
    player = repo.load_player()
    if player["gold"] < neg["agreed_price"]:
        raise ValueError("insufficient gold")
    bundle = neg["materials"]

    # 재료 인벤토리 추가
    for m in bundle["materials"]:
        repo.add_inventory(m["material_id"], m["qty"])

    # 무기는 weapons 행을 새로 insert (owner='player')
    if bundle.get("weapon"):
        w = bundle["weapon"]
        repo.insert_weapon({
            "owner": "player",
            "name": w["name"], "type": w["type"], "rarity": w["rarity"],
            "sharpness": w["sharpness"], "attribute": w.get("attribute"),
            "skill": w["skill"], "str_req": w["str_req"], "mag_req": w["mag_req"],
            "enhancement_level": 0, "materials_used": [], "created_day": player["current_day"],
        })

    # 골드 차감 + 평판 +1 + phase advance
    repo.update_player(
        gold=player["gold"] - neg["agreed_price"],
        reputation=player["reputation"] + 1,
        current_phase=state_machine.next_phase(player["current_phase"]),
    )

    # merchant_today outcome=done
    repo.update_merchant_today(neg["counterparty_id"], outcome="done")

    # 이벤트 기록
    repo.insert_day_event(
        day=player["current_day"], phase=player["current_phase"], kind="buy",
        payload={"price": neg["agreed_price"], "materials": bundle["materials"],
                 "weapon": bundle.get("weapon")},
    )


def player_accept_buy_counter(neg_id: int) -> int:
    neg = repo.get_negotiation(neg_id)
    if neg["outcome"] != "open":
        raise ValueError(f"negotiation already {neg['outcome']}")
    merchant_rounds = [r for r in neg["rounds"] if r["role"] == "merchant" and r.get("price") is not None]
    if not merchant_rounds:
        raise ValueError("no merchant counter to accept")
    agreed = int(merchant_rounds[-1]["price"])
    repo.update_negotiation(neg_id, outcome="accepted", agreed_price=agreed)
    return agreed


def player_reject_buy(neg_id: int) -> None:
    neg = repo.get_negotiation(neg_id)
    if neg["outcome"] != "open":
        raise ValueError(f"negotiation already {neg['outcome']}")
    repo.update_negotiation(neg_id, outcome="rejected")
    player_now = repo.load_player()
    # 협상 후 거절만 평판 -1 (architecture.md §7.2). rounds가 있으면 협상이 있었다는 뜻
    rep_delta = -1 if neg["rounds"] else 0
    repo.update_player(
        reputation=player_now["reputation"] + rep_delta,
        current_phase=state_machine.next_phase(player_now["current_phase"]),
    )
    repo.update_merchant_today(neg["counterparty_id"], outcome="done")


def _client_or_repo_get_merchant(merchant_id: int) -> dict[str, Any]:
    """merchant_today 행 로드 헬퍼 — 모듈 의존성을 간결히 하기 위해 분리."""
    from . import repo as _repo
    c = _repo._client()
    return c.table("merchants_today").select("*").eq("id", merchant_id).single().execute().data
```

- [ ] **Step 3: 테스트 실행**

```bash
cd /home/afraidnot/dev/smith-tycoon/backend && ./.venv/bin/pytest tests/test_negotiation.py -v
```
Expected: 6 PASS (기존 4 + 신규 2).

- [ ] **Step 4: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add backend/app/negotiation.py backend/tests/test_negotiation.py && git commit -m "feat(negotiation): buy flow (step_buy, finalize_buy, accept/reject counter)"
```

---

## Task 9: api/merchant.py + 라우터 등록 + skip 엔드포인트

**Files:**
- Create: `backend/app/api/merchant.py`
- Modify: `backend/app/api/forge.py`
- Modify: `backend/app/models.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: `backend/app/models.py`에 추가**

`backend/app/models.py` 끝에 append:

```python


class MerchantNegotiateRequest(BaseModel):
    merchant_id: int
    price_offered: int
    player_message: str
    negotiation_id: int | None = None


class MerchantSkipRequest(BaseModel):
    merchant_id: int
```

- [ ] **Step 2: `backend/app/api/merchant.py` 작성**

```python
from fastapi import APIRouter, HTTPException
from .. import repo, negotiation, merchant, state_machine
from ..models import MerchantNegotiateRequest, NegotiateResponse, FinalizeRequest, MerchantSkipRequest

router = APIRouter()


def _ensure_merchant_today(day: int) -> dict:
    m = repo.get_merchant_today(day)
    if m is None:
        bundle = merchant.generate_today(day)
        m = repo.insert_merchant_today({"day": day, **bundle, "outcome": "pending"})
    return m


@router.post("/merchant/negotiate", response_model=NegotiateResponse)
async def post_merchant_negotiate(req: MerchantNegotiateRequest):
    player = repo.load_player()
    try:
        state_machine.assert_phase(player["current_phase"], "merchant_negotiate")
    except state_machine.PhaseError:
        raise HTTPException(400, detail={"error": "wrong_phase", "current_phase": player["current_phase"]})

    m = _ensure_merchant_today(player["current_day"])
    if m["id"] != req.merchant_id:
        raise HTTPException(400, detail={"error": "merchant_mismatch"})

    result = await negotiation.step_buy(m["id"], req.price_offered, req.player_message,
                                         neg_id=req.negotiation_id)
    return result


@router.post("/merchant/negotiate/finalize")
def post_merchant_finalize(req: FinalizeRequest):
    try:
        negotiation.finalize_buy(req.negotiation_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_finalize", "message": str(e)})
    player = repo.load_player()
    return {"ok": True, "next_phase": player["current_phase"]}


@router.post("/merchant/player_accept")
def post_merchant_player_accept(req: FinalizeRequest):
    try:
        agreed = negotiation.player_accept_buy_counter(req.negotiation_id)
        negotiation.finalize_buy(req.negotiation_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_accept", "message": str(e)})
    player = repo.load_player()
    return {"ok": True, "agreed_price": agreed, "next_phase": player["current_phase"]}


@router.post("/merchant/player_reject")
def post_merchant_player_reject(req: FinalizeRequest):
    try:
        negotiation.player_reject_buy(req.negotiation_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_reject", "message": str(e)})
    player = repo.load_player()
    return {"ok": True, "next_phase": player["current_phase"]}


@router.post("/merchant/skip")
def post_merchant_skip():
    """상인 협상을 건너뛰고 다음 phase로. 평판 변화 없음."""
    player = repo.load_player()
    try:
        state_machine.assert_phase(player["current_phase"], "merchant_negotiate")
    except state_machine.PhaseError:
        raise HTTPException(400, detail={"error": "wrong_phase", "current_phase": player["current_phase"]})
    m = _ensure_merchant_today(player["current_day"])
    repo.update_merchant_today(m["id"], outcome="done")
    repo.update_player(current_phase=state_machine.next_phase(player["current_phase"]))
    return {"ok": True, "next_phase": repo.load_player()["current_phase"]}
```

- [ ] **Step 3: `backend/app/api/forge.py` 갱신 — forge_open_2 허용 + skip 엔드포인트**

```python
from fastapi import APIRouter, HTTPException
from .. import repo, forge, state_machine
from ..models import ForgeRequest, WeaponOut

router = APIRouter()

FORGE_PHASES = ["forge_open", "forge_open_2"]


@router.post("/forge", response_model=WeaponOut)
async def post_forge(req: ForgeRequest):
    player = repo.load_player()
    try:
        state_machine.assert_phase_in(player["current_phase"], FORGE_PHASES)
    except state_machine.PhaseError:
        raise HTTPException(400, detail={"error": "wrong_phase", "current_phase": player["current_phase"]})

    try:
        weapon = await forge.craft(req.weapon_type, {m.material_id: m.qty for m in req.materials})
    except ValueError as e:
        raise HTTPException(400, detail={"error": "insufficient_materials", "message": str(e)})

    repo.insert_day_event(day=player["current_day"], phase=player["current_phase"],
                          kind="forge", payload={"weapon_id": weapon["id"], "name": weapon["name"]})

    repo.update_player(current_phase=state_machine.next_phase(player["current_phase"]))
    return weapon


@router.post("/forge/skip")
def post_forge_skip():
    player = repo.load_player()
    try:
        state_machine.assert_phase_in(player["current_phase"], FORGE_PHASES)
    except state_machine.PhaseError:
        raise HTTPException(400, detail={"error": "wrong_phase", "current_phase": player["current_phase"]})
    repo.update_player(current_phase=state_machine.next_phase(player["current_phase"]))
    return {"ok": True, "next_phase": repo.load_player()["current_phase"]}
```

- [ ] **Step 4: `backend/app/main.py` — merchant 라우터 등록**

```python
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import (
    forge as forge_api, negotiate as negotiate_api, battle as battle_api,
    state as state_api, game as game_api, merchant as merchant_api,
)
from .llm.client import session_totals

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

app = FastAPI(title="Smith Tycoon API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(state_api.router)
app.include_router(forge_api.router)
app.include_router(negotiate_api.router)
app.include_router(battle_api.router)
app.include_router(game_api.router)
app.include_router(merchant_api.router)


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/llm/usage")
def llm_usage():
    return session_totals()
```

- [ ] **Step 5: 회귀 테스트**

```bash
cd /home/afraidnot/dev/smith-tycoon/backend && ./.venv/bin/pytest -v
```
Expected: 모든 테스트 PASS.

- [ ] **Step 6: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add backend/app/models.py backend/app/api/merchant.py backend/app/api/forge.py backend/app/main.py && git commit -m "feat(api): merchant endpoints, forge_open_2, forge/skip"
```

---

## Task 10: api/negotiate.py + api/battle.py — 다중 hero phase 허용

**Files:**
- Modify: `backend/app/api/negotiate.py`
- Modify: `backend/app/api/battle.py`

- [ ] **Step 1: `backend/app/api/negotiate.py` 갱신**

```python
from fastapi import APIRouter, HTTPException
from .. import repo, negotiation, state_machine
from ..models import NegotiateRequest, NegotiateResponse, FinalizeRequest

router = APIRouter()

NEGOTIATE_PHASES = ["hero1_negotiate", "hero2_negotiate", "hero3_negotiate"]


def _hero_index_for_phase(phase: str) -> int:
    return {"hero1_negotiate": 0, "hero2_negotiate": 1, "hero3_negotiate": 2}[phase]


@router.post("/negotiate", response_model=NegotiateResponse)
async def post_negotiate(req: NegotiateRequest):
    player = repo.load_player()
    try:
        state_machine.assert_phase_in(player["current_phase"], NEGOTIATE_PHASES)
    except state_machine.PhaseError:
        raise HTTPException(400, detail={"error": "wrong_phase",
                                          "current_phase": player["current_phase"]})

    weapon = repo.get_weapon(req.weapon_id)
    if weapon["owner"] != "player":
        raise HTTPException(400, detail={"error": "weapon_not_owned"})

    # state.py가 GET /state에서 오늘의 hero들을 결정·persist하므로 여기선 단순 조회
    from .. import hero_registry
    todays = hero_registry.heroes_for_today(player["current_day"])
    idx = _hero_index_for_phase(player["current_phase"])
    hero_id = todays[idx]["id"]

    result = await negotiation.step_sell(req.weapon_id, hero_id, req.price_offered,
                                         req.player_message, neg_id=req.negotiation_id)
    return result


@router.post("/negotiate/finalize")
def post_finalize(req: FinalizeRequest):
    try:
        negotiation.finalize_sale(req.negotiation_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_finalize", "message": str(e)})
    player = repo.load_player()
    return {"ok": True, "next_phase": player["current_phase"]}


@router.post("/negotiate/player_accept")
def post_player_accept(req: FinalizeRequest):
    try:
        agreed = negotiation.player_accept_counter(req.negotiation_id)
        negotiation.finalize_sale(req.negotiation_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_accept", "message": str(e)})
    player = repo.load_player()
    return {"ok": True, "agreed_price": agreed, "next_phase": player["current_phase"]}


@router.post("/negotiate/player_reject")
def post_player_reject(req: FinalizeRequest):
    try:
        negotiation.player_reject(req.negotiation_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_reject", "message": str(e)})
    player = repo.load_player()
    return {"ok": True, "next_phase": player["current_phase"]}
```

- [ ] **Step 2: `backend/app/api/battle.py` 갱신**

```python
from fastapi import APIRouter, HTTPException
from .. import repo, combat, state_machine
from ..models import BattleResponse

router = APIRouter()

BATTLE_PHASES = ["hero1_battle", "hero2_battle", "hero3_battle"]


def _hero_index_for_phase(phase: str) -> int:
    return {"hero1_battle": 0, "hero2_battle": 1, "hero3_battle": 2}[phase]


@router.post("/battle", response_model=BattleResponse)
async def post_battle():
    player = repo.load_player()
    try:
        state_machine.assert_phase_in(player["current_phase"], BATTLE_PHASES)
    except state_machine.PhaseError:
        raise HTTPException(400, detail={"error": "wrong_phase",
                                          "current_phase": player["current_phase"]})

    from .. import hero_registry
    todays = hero_registry.heroes_for_today(player["current_day"])
    idx = _hero_index_for_phase(player["current_phase"])
    hero = todays[idx]

    # 이 hero가 직전 협상에서 산 무기 찾기 — 해당 hero가 가장 최근에 받은 sold 무기
    # MVP 한계: 협상-전투 1:1 쌍이므로 sold 중 마지막을 그 hero의 무기로 간주
    sold = repo.list_sold_weapons()
    weapon_id = sold[-1]["id"] if sold else None
    return await combat.run_battle(hero["id"], weapon_id)
```

- [ ] **Step 3: 회귀 테스트**

```bash
cd /home/afraidnot/dev/smith-tycoon/backend && ./.venv/bin/pytest -v
```
Expected: 모든 테스트 PASS.

- [ ] **Step 4: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add backend/app/api/negotiate.py backend/app/api/battle.py && git commit -m "feat(api): allow hero1/2/3 phases for negotiate and battle"
```

---

## Task 11: day_summary 모듈 + api/day.py

**Files:**
- Create: `backend/app/day_summary.py`
- Create: `backend/app/api/day.py`
- Create: `backend/tests/test_day_summary.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 테스트 작성 — `backend/tests/test_day_summary.py`**

```python
from app.day_summary import summarize_events


def test_summarize_events_counts_kinds():
    events = [
        {"kind": "forge",  "payload": {"name": "검A"}},
        {"kind": "sale",   "payload": {"price": 1000}},
        {"kind": "battle", "payload": {"outcomes": {"hero": "survived"}, "rep_delta": 2}},
        {"kind": "battle", "payload": {"outcomes": {"hero": "injured"},  "rep_delta": 0}},
        {"kind": "buy",    "payload": {"price": 800}},
    ]
    s = summarize_events(events)
    assert s["forges"] == 1
    assert s["sales"] == 1
    assert s["buys"] == 1
    assert s["battles"] == 2
    assert s["heroes_survived"] == 1
    assert s["heroes_injured"] == 1
    assert s["heroes_died"] == 0


def test_summarize_events_empty():
    s = summarize_events([])
    assert s == {"forges": 0, "sales": 0, "buys": 0, "battles": 0,
                 "heroes_survived": 0, "heroes_injured": 0, "heroes_died": 0,
                 "rep_delta": 0, "gold_delta": 0}
```

- [ ] **Step 2: 테스트 실행 (FAIL)**

```bash
cd /home/afraidnot/dev/smith-tycoon/backend && ./.venv/bin/pytest tests/test_day_summary.py -v
```
Expected: ModuleNotFoundError.

- [ ] **Step 3: `backend/app/day_summary.py` 작성**

```python
from __future__ import annotations
from typing import Any
from . import repo


def summarize_events(events: list[dict[str, Any]]) -> dict[str, int]:
    s = {"forges": 0, "sales": 0, "buys": 0, "battles": 0,
         "heroes_survived": 0, "heroes_injured": 0, "heroes_died": 0,
         "rep_delta": 0, "gold_delta": 0}
    for e in events:
        k = e["kind"]; p = e.get("payload", {})
        if k == "forge":  s["forges"] += 1
        elif k == "sale": s["sales"] += 1; s["gold_delta"] += int(p.get("price", 0))
        elif k == "buy":  s["buys"]  += 1; s["gold_delta"] -= int(p.get("price", 0))
        elif k == "battle":
            s["battles"] += 1
            out = p.get("outcomes", {})
            if out.get("hero") == "survived": s["heroes_survived"] += 1
            elif out.get("hero") == "injured": s["heroes_injured"] += 1
            elif out.get("hero") == "died":    s["heroes_died"] += 1
            s["rep_delta"] += int(p.get("rep_delta", 0))
    return s


def build(day: int) -> dict[str, Any]:
    events = repo.list_day_events(day)
    summary = summarize_events(events)
    return {"day": day, "events": events, "summary": summary}
```

- [ ] **Step 4: `backend/app/api/day.py` 작성**

```python
from fastapi import APIRouter, HTTPException
from .. import repo, day_summary, state_machine
from ..models import FinalizeRequest  # 빈 body로 충분하면 일반 dict 응답

router = APIRouter()


@router.get("/day/summary")
def get_summary():
    player = repo.load_player()
    return day_summary.build(player["current_day"])


@router.post("/day/next")
def post_next_day():
    player = repo.load_player()
    if player["current_phase"] != "day_summary":
        raise HTTPException(400, detail={"error": "wrong_phase",
                                          "current_phase": player["current_phase"]})
    state_machine.advance_to_next_day(player)
    repo.update_player(current_day=player["current_day"],
                       current_phase=player["current_phase"])
    return {"ok": True, "current_day": player["current_day"],
            "current_phase": player["current_phase"]}
```

- [ ] **Step 5: `backend/app/main.py`에 day 라우터 등록**

기존 main.py의 import와 include_router 라인에 추가:

```python
from .api import (
    forge as forge_api, negotiate as negotiate_api, battle as battle_api,
    state as state_api, game as game_api, merchant as merchant_api, day as day_api,
)
...
app.include_router(day_api.router)
```

- [ ] **Step 6: 테스트 PASS**

```bash
cd /home/afraidnot/dev/smith-tycoon/backend && ./.venv/bin/pytest -v
```
Expected: 모든 테스트 PASS.

- [ ] **Step 7: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add backend/app/day_summary.py backend/app/api/day.py backend/app/main.py backend/tests/test_day_summary.py && git commit -m "feat(day): day_summary module + GET /day/summary + POST /day/next"
```

---

## Task 12: state.py + game.py — 다일 컨텍스트 + hero_registry 통합

**Files:**
- Modify: `backend/app/api/state.py`
- Modify: `backend/app/api/game.py`

- [ ] **Step 1: `backend/app/api/state.py` 갱신**

```python
from fastapi import APIRouter
from .. import repo, hero_registry, merchant as merchant_module

router = APIRouter()

NEGOTIATE_PHASES = ["hero1_negotiate", "hero2_negotiate", "hero3_negotiate"]
BATTLE_PHASES = ["hero1_battle", "hero2_battle", "hero3_battle"]


def _hero_index(phase: str) -> int | None:
    mapping = {"hero1_negotiate": 0, "hero1_battle": 0,
               "hero2_negotiate": 1, "hero2_battle": 1,
               "hero3_negotiate": 2, "hero3_battle": 2}
    return mapping.get(phase)


@router.get("/state")
def get_state():
    player = repo.load_player()
    if player is None:
        return {"player": None, "inventory": [], "weapons": [],
                "hero": None, "merchant": None}

    inventory = repo.load_inventory()
    weapons = repo.load_player_weapons()

    hero = None
    if player["current_phase"] in NEGOTIATE_PHASES + BATTLE_PHASES:
        todays = hero_registry.heroes_for_today(player["current_day"])
        idx = _hero_index(player["current_phase"])
        if idx is not None and idx < len(todays):
            hero = todays[idx]

    merchant_today = None
    if player["current_phase"] == "merchant_negotiate":
        m = repo.get_merchant_today(player["current_day"])
        if m is None:
            bundle = merchant_module.generate_today(player["current_day"])
            m = repo.insert_merchant_today({"day": player["current_day"], **bundle,
                                             "outcome": "pending"})
        merchant_today = m

    return {
        "player": player,
        "inventory": inventory,
        "weapons": weapons,
        "hero": hero,
        "merchant": merchant_today,
    }
```

- [ ] **Step 2: `backend/app/api/game.py` 갱신 — hero 생성을 hero_registry에 위임**

```python
from fastapi import APIRouter
from .. import repo, hero_registry

router = APIRouter()


@router.post("/game/reset")
def post_reset():
    repo.reset_game()
    # Plan 1에서는 단일 hero를 만들었지만, Plan 2부터는 매일 lazily 생성하므로
    # reset 시점엔 hero 없이 시작 — heroes_for_today가 첫 day에 호출되면서 채움.
    return {"ok": True}
```

- [ ] **Step 3: 회귀**

```bash
cd /home/afraidnot/dev/smith-tycoon/backend && ./.venv/bin/pytest -v
```
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add backend/app/api/state.py backend/app/api/game.py && git commit -m "feat(api): state exposes merchant + day-aware hero; game/reset defers heroes to registry"
```

---

## Task 13: 통합 테스트 — 하루 골든 패스

**Files:**
- Create: `backend/tests/test_integration_day.py`

- [ ] **Step 1: `backend/tests/test_integration_day.py` 작성**

```python
import pytest
from unittest.mock import patch
from app import forge, negotiation, combat, merchant


class FakeRepo:
    def __init__(self):
        self.player = {"id": 1, "gold": 5000, "reputation": 0, "current_day": 1,
                       "current_phase": "forge_open", "craft_power": 0}
        self.inventory = [
            {"material_id": 1, "qty": 5, "name": "나뭇가지", "category": "일반", "attribute": "바람", "base_price": 5},
            {"material_id": 4, "qty": 5, "name": "철덩이",   "category": "일반", "attribute": "금",   "base_price": 50},
            {"material_id": 8, "qty": 3, "name": "강철",     "category": "일반", "attribute": "금",   "base_price": 120},
        ]
        self.weapons: list = []
        self.heroes = []
        self.negs: list = []
        self.battles: list = []
        self.merchants: list = []
        self.day_events: list = []
        self._wid = 100
        self._nid = 0
        self._mid = 0
        self._bid = 0

    # players
    def load_player(self): return self.player
    def update_player(self, **f): self.player.update(f)

    # inventory
    def load_inventory(self): return list(self.inventory)
    def deduct_materials(self, mq):
        for mid, q in mq.items():
            row = next(r for r in self.inventory if r["material_id"] == mid)
            row["qty"] -= q
    def add_inventory(self, mid, qty):
        for r in self.inventory:
            if r["material_id"] == mid:
                r["qty"] += qty
                return
        self.inventory.append({"material_id": mid, "qty": qty, "name": "?",
                               "category": "일반", "attribute": None, "base_price": 50})

    # weapons
    def insert_weapon(self, w):
        self._wid += 1
        w = {**w, "id": self._wid, "player_id": 1}
        self.weapons.append(w); return w
    def get_weapon(self, wid): return next(w for w in self.weapons if w["id"] == wid)
    def list_sold_weapons(self): return [w for w in self.weapons if w["owner"] == "sold"]
    def list_player_weapons(self): return [w for w in self.weapons if w["owner"] == "player"]
    def transfer_weapon_to_hero(self, wid, _):
        for w in self.weapons:
            if w["id"] == wid: w["owner"] = "sold"

    # heroes
    def insert_hero(self, h):
        h = {**h, "id": 10 + len(self.heroes)}
        self.heroes.append(h); return h
    def get_hero(self, hid): return next(h for h in self.heroes if h["id"] == hid)
    def update_hero(self, hid, **f): self.get_hero(hid).update(f)
    def list_alive_heroes(self): return [h for h in self.heroes if h["status"] == "alive"]
    def list_alive_heroes_ready(self, day):
        return [h for h in self.heroes if h["status"] == "alive"
                and (h.get("return_day") is None or h["return_day"] <= day)]

    # negotiations
    def insert_negotiation(self, n):
        self._nid += 1
        n = {**n, "id": self._nid, "player_id": 1}
        self.negs.append(n); return n
    def get_negotiation(self, nid): return next(n for n in self.negs if n["id"] == nid)
    def update_negotiation(self, nid, **f): self.get_negotiation(nid).update(f)

    # merchants_today
    def get_merchant_today(self, day):
        return next((m for m in self.merchants if m["day"] == day), None)
    def insert_merchant_today(self, m):
        self._mid += 1
        m = {**m, "id": self._mid, "player_id": 1}
        self.merchants.append(m); return m
    def update_merchant_today(self, mid, **f):
        next(m for m in self.merchants if m["id"] == mid).update(f)

    # day_events
    def insert_day_event(self, day, phase, kind, payload):
        self._bid += 1
        self.day_events.append({"id": self._bid, "day": day, "phase": phase,
                                "kind": kind, "payload": payload})
    def list_day_events(self, day):
        return [e for e in self.day_events if e["day"] == day]

    # battles
    def insert_battle(self, b):
        b = {**b, "id": len(self.battles) + 1, "player_id": 1}
        self.battles.append(b); return b


@pytest.mark.asyncio
async def test_day_one_golden_path():
    fake = FakeRepo()
    # seed 한 hero — heroes_for_today가 부족하면 더 만들지만 여기선 미리 3명 채움
    for i in range(3):
        fake.heroes.append({
            "id": 10 + i, "name": str(100 + i), "job": "검사",
            "str": 12, "mag": 5, "gold": 2000, "mood": "여유로움",
            "personality_tags": ["호탕"], "affinity": 0, "status": "alive",
            "return_day": None, "history": [],
        })
    from app import repo as repo_mod
    from app import hero_registry, day_summary

    with patch.object(forge, "repo", fake), \
         patch.object(negotiation, "repo", fake), \
         patch.object(combat, "repo", fake), \
         patch.object(hero_registry, "repo", fake), \
         patch.object(day_summary, "repo", fake), \
         patch("app.negotiation._client_or_repo_get_merchant",
               side_effect=lambda mid: next(m for m in fake.merchants if m["id"] == mid)):

        # forge_open — 무기 제작
        weapon = await forge.craft("양손검", {1: 2, 4: 2})
        assert weapon["owner"] == "player"
        fake.update_player(current_phase="hero1_negotiate")

        # hero1 협상 — accept
        todays = hero_registry.heroes_for_today(1)
        h1 = todays[0]
        r = await negotiation.step_sell(weapon["id"], h1["id"], 1500, "괜찮으시오?", neg_id=None)
        assert r["decision"] == "accept"
        negotiation.finalize_sale(r["negotiation_id"])
        assert fake.player["current_phase"] == "hero1_battle"

        # hero1 전투
        b = await combat.run_battle(h1["id"], weapon["id"])
        assert "outcomes" in b
        assert fake.player["current_phase"] == "merchant_negotiate"

        # 상인 — generate_today + skip 시뮬레이션
        bundle = merchant.generate_today(day=1, seed=1)
        m_row = fake.insert_merchant_today({"day": 1, **bundle, "outcome": "pending"})
        fake.update_merchant_today(m_row["id"], outcome="done")
        fake.update_player(current_phase="hero2_negotiate")

        # hero2: 무기가 없으므로 협상 단계는 시뮬레이션상 건너뛰고 (UI는 안내 메시지),
        # 직접 hero2_battle phase로 전이해서 맨손 전투를 검증
        h2 = todays[1]
        fake.update_player(current_phase="hero2_battle")
        b2 = await combat.run_battle(h2["id"], None)
        assert "outcomes" in b2
        assert fake.player["current_phase"] == "forge_open_2"

        # forge_open_2 skip
        fake.update_player(current_phase="hero3_negotiate")

        # hero3 — accept (마지막 무기 사용)
        # weapon[0]은 이미 sold. 새 무기 안 만들었으므로 hero3는 무기 없이 전투
        fake.update_player(current_phase="hero3_battle")
        b3 = await combat.run_battle(todays[2]["id"], None)
        assert fake.player["current_phase"] == "day_summary"

        # day_summary build
        summary = day_summary.build(1)
        assert summary["day"] == 1
        assert summary["summary"]["battles"] == 3
        assert summary["summary"]["forges"] == 1
        assert summary["summary"]["sales"] == 1
```

- [ ] **Step 2: 통합 테스트 실행**

```bash
cd /home/afraidnot/dev/smith-tycoon/backend && ./.venv/bin/pytest tests/test_integration_day.py -v
```
Expected: 1 PASS.

만약 `_client_or_repo_get_merchant`가 not found 등 import 에러 나면 negotiation.py에 그 함수가 정의돼 있는지 재확인.

- [ ] **Step 3: 전체 회귀**

```bash
cd /home/afraidnot/dev/smith-tycoon/backend && ./.venv/bin/pytest -v
```
Expected: 모든 테스트 PASS.

- [ ] **Step 4: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add backend/tests/test_integration_day.py && git commit -m "test(backend): day-1 golden path integration test"
```

---

## Task 14: 프론트 types + api wrapper 확장

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/api.ts`

- [ ] **Step 1: `frontend/src/types.ts` 갱신 — `MerchantInventoryWeapon`, `MerchantToday`, `DaySummaryResponse` 추가**

```typescript
export interface Material {
  material_id: number;
  qty: number;
  name: string;
  category: string;
  attribute: string | null;
  base_price: number;
}

export interface Weapon {
  id: number;
  name: string;
  type: string;
  rarity: number;
  sharpness: number;
  attribute: string | null;
  skill: string;
  str_req: number;
  mag_req: number;
}

export interface Hero {
  id: number;
  name: string;
  job: string;
  str: number;
  mag: number;
  gold: number;
  mood: string;
  personality_tags: string[];
  affinity: number;
}

export interface Player {
  id: number;
  gold: number;
  reputation: number;
  current_day: number;
  current_phase: string;
}

export interface MerchantInventoryMaterial {
  material_id: number;
  name: string;
  category: string;
  attribute: string | null;
  base_price: number;
  qty: number;
  asking_price: number;
}

export interface MerchantInventoryWeapon {
  name: string;
  type: string;
  rarity: number;
  sharpness: number;
  attribute: string | null;
  skill: string;
  str_req: number;
  mag_req: number;
  asking_price: number;
}

export interface MerchantToday {
  id: number;
  day: number;
  materials: MerchantInventoryMaterial[];
  weapon: MerchantInventoryWeapon | null;
  outcome: "pending" | "done";
}

export interface StateResponse {
  player: Player | null;
  inventory: Material[];
  weapons: Weapon[];
  hero: Hero | null;
  merchant: MerchantToday | null;
}

export interface NegotiateResponse {
  negotiation_id: number;
  decision: "accept" | "reject" | "counter";
  counter_price: number | null;
  message: string;
}

export interface BattleResponse {
  script: string;
  outcomes: { hero: string; weapon: string; demon: string };
  next_phase: string;
}

export interface DayEvent {
  id: number;
  day: number;
  phase: string;
  kind: string;
  payload: Record<string, unknown>;
}

export interface DaySummaryResponse {
  day: number;
  events: DayEvent[];
  summary: {
    forges: number; sales: number; buys: number; battles: number;
    heroes_survived: number; heroes_injured: number; heroes_died: number;
    rep_delta: number; gold_delta: number;
  };
}
```

- [ ] **Step 2: `frontend/src/api.ts` 갱신**

```typescript
import type {
  StateResponse, Weapon, NegotiateResponse, BattleResponse, DaySummaryResponse,
} from "./types";

const BASE = "/api";

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) {
    const detail = await r.json().catch(() => ({}));
    throw Object.assign(new Error("api_error"), { detail, status: r.status });
  }
  return r.json();
}

export const api = {
  getState: () => request<StateResponse>("GET", "/state"),
  resetGame: () => request<{ ok: true }>("POST", "/game/reset"),

  forge: (weapon_type: string, materials: { material_id: number; qty: number }[]) =>
    request<Weapon>("POST", "/forge", { weapon_type, materials }),
  forgeSkip: () =>
    request<{ ok: true; next_phase: string }>("POST", "/forge/skip"),

  negotiate: (weapon_id: number, price_offered: number, player_message: string, negotiation_id: number | null = null) =>
    request<NegotiateResponse>("POST", "/negotiate", { weapon_id, price_offered, player_message, negotiation_id }),
  finalize: (negotiation_id: number) =>
    request<{ ok: true; next_phase: string }>("POST", "/negotiate/finalize", { negotiation_id }),
  playerAccept: (negotiation_id: number) =>
    request<{ ok: true; agreed_price: number; next_phase: string }>("POST", "/negotiate/player_accept", { negotiation_id }),
  playerReject: (negotiation_id: number) =>
    request<{ ok: true; next_phase: string }>("POST", "/negotiate/player_reject", { negotiation_id }),

  battle: () => request<BattleResponse>("POST", "/battle"),

  merchantNegotiate: (merchant_id: number, price_offered: number, player_message: string, negotiation_id: number | null = null) =>
    request<NegotiateResponse>("POST", "/merchant/negotiate", { merchant_id, price_offered, player_message, negotiation_id }),
  merchantFinalize: (negotiation_id: number) =>
    request<{ ok: true; next_phase: string }>("POST", "/merchant/negotiate/finalize", { negotiation_id }),
  merchantPlayerAccept: (negotiation_id: number) =>
    request<{ ok: true; agreed_price: number; next_phase: string }>("POST", "/merchant/player_accept", { negotiation_id }),
  merchantPlayerReject: (negotiation_id: number) =>
    request<{ ok: true; next_phase: string }>("POST", "/merchant/player_reject", { negotiation_id }),
  merchantSkip: () =>
    request<{ ok: true; next_phase: string }>("POST", "/merchant/skip"),

  daySummary: () => request<DaySummaryResponse>("GET", "/day/summary"),
  nextDay: () => request<{ ok: true; current_day: number; current_phase: string }>("POST", "/day/next"),
};
```

- [ ] **Step 3: 타입체크**

```bash
cd /home/afraidnot/dev/smith-tycoon/frontend && npx tsc --noEmit
```
Expected: 없음.

- [ ] **Step 4: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add frontend/src/types.ts frontend/src/api.ts && git commit -m "feat(frontend): Plan 2 types and API client extensions"
```

---

## Task 15: ForgePanel skip 버튼 + SidePanel day 표시

**Files:**
- Modify: `frontend/src/components/ForgePanel.tsx`
- Modify: `frontend/src/components/SidePanel.tsx`

- [ ] **Step 1: `frontend/src/components/ForgePanel.tsx` — skip 버튼 추가**

기존 파일의 return 안 마지막 `<button>제작하기` 옆에 skip 버튼 추가. 전체 파일을 다음으로 교체:

```typescript
import { useState } from "react";
import { api } from "../api";
import type { Material } from "../types";

const WEAPON_TYPES = ["한손검", "양손검", "한손둔기", "양손둔기", "마법지팡이", "방패", "단도", "표창", "총"];

export function ForgePanel({ inventory, onDone }: { inventory: Material[]; onDone: () => void }) {
  const [picks, setPicks] = useState<Record<number, number>>({});
  const [type, setType] = useState(WEAPON_TYPES[0]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const change = (mid: number, delta: number) => {
    setPicks((p) => {
      const cur = (p[mid] ?? 0) + delta;
      const max = inventory.find((m) => m.material_id === mid)?.qty ?? 0;
      const next = Math.max(0, Math.min(max, cur));
      const out = { ...p };
      if (next === 0) delete out[mid]; else out[mid] = next;
      return out;
    });
  };

  const submit = async () => {
    setBusy(true); setErr(null);
    try {
      const materials = Object.entries(picks).map(([k, v]) => ({ material_id: Number(k), qty: v }));
      if (!materials.length) throw new Error("재료를 1개 이상 선택하세요");
      await api.forge(type, materials);
      onDone();
    } catch (e: unknown) {
      setErr((e as Error).message);
    } finally { setBusy(false); }
  };

  const skip = async () => {
    setBusy(true); setErr(null);
    try { await api.forgeSkip(); onDone(); }
    catch (e: unknown) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  return (
    <div>
      <h2>제작</h2>
      <div>
        무기 종류:
        <select value={type} onChange={(e) => setType(e.target.value)}>
          {WEAPON_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>

      <h4>재료 선택</h4>
      {inventory.map((m) => (
        <div key={m.material_id} className="material-row">
          <span style={{ flex: 1 }}>{m.name} <small>({m.category}, 보유 {m.qty})</small></span>
          <button className="btn" onClick={() => change(m.material_id, -1)}>−</button>
          <span style={{ width: 24, textAlign: "center" }}>{picks[m.material_id] ?? 0}</span>
          <button className="btn" onClick={() => change(m.material_id, +1)}>+</button>
        </div>
      ))}

      <div style={{ marginTop: 16, display: "flex", gap: 8 }}>
        <button className="btn" onClick={submit} disabled={busy}>{busy ? "제작 중..." : "제작하기"}</button>
        <button className="btn" onClick={skip} disabled={busy}>건너뛰기</button>
      </div>
      {err && <p style={{ color: "red" }}>{err}</p>}
    </div>
  );
}
```

- [ ] **Step 2: `frontend/src/components/SidePanel.tsx` — day 표시 추가**

기존 SidePanel에서 player 섹션을 다음과 같이 변경:

```typescript
import type { StateResponse } from "../types";

export function SidePanel({ state, onReset }: { state: StateResponse; onReset: () => void }) {
  if (!state.player) return null;
  return (
    <div className="side">
      <h3>플레이어</h3>
      <p>일차: <strong>Day {state.player.current_day} / 5</strong></p>
      <p>금화: {state.player.gold}</p>
      <p>평판: {state.player.reputation}</p>
      <p>Phase: <code>{state.player.current_phase}</code></p>

      <h4>인벤토리</h4>
      <ul>
        {state.inventory.map((m) => (
          <li key={m.material_id}>{m.name} × {m.qty} <small>({m.category})</small></li>
        ))}
      </ul>

      <h4>진열장</h4>
      {state.weapons.length === 0 ? <p><em>(없음)</em></p> : (
        <ul>
          {state.weapons.map((w) => (
            <li key={w.id}>{w.name} ({w.type})</li>
          ))}
        </ul>
      )}

      <button className="btn" onClick={onReset} style={{ marginTop: 16 }}>새 게임</button>
    </div>
  );
}
```

- [ ] **Step 3: 타입체크**

```bash
cd /home/afraidnot/dev/smith-tycoon/frontend && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add frontend/src/components/ForgePanel.tsx frontend/src/components/SidePanel.tsx && git commit -m "feat(frontend): forge skip button + day display in SidePanel"
```

---

## Task 16: MerchantPanel + MerchantNegotiation

**Files:**
- Create: `frontend/src/components/MerchantPanel.tsx`
- Create: `frontend/src/components/MerchantNegotiation.tsx`

- [ ] **Step 1: `frontend/src/components/MerchantPanel.tsx`**

```typescript
import { useState } from "react";
import { api } from "../api";
import type { MerchantToday } from "../types";
import { MerchantNegotiation } from "./MerchantNegotiation";

export function MerchantPanel({ merchant, onDone }: { merchant: MerchantToday; onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [entering, setEntering] = useState(false);

  const skip = async () => {
    setBusy(true); setErr(null);
    try { await api.merchantSkip(); onDone(); }
    catch (e: unknown) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  if (entering) {
    return <MerchantNegotiation merchant={merchant} onDone={onDone} />;
  }

  const total = merchant.materials.reduce((s, m) => s + m.asking_price, 0)
              + (merchant.weapon?.asking_price ?? 0);

  return (
    <div>
      <h2>상인 방문</h2>
      <p>오늘의 묶음 (총 시세 {total} 골드):</p>
      <ul>
        {merchant.materials.map((m) => (
          <li key={m.material_id}>{m.name} × {m.qty} — {m.asking_price} 골드 <small>({m.category})</small></li>
        ))}
        {merchant.weapon && (
          <li><strong>{merchant.weapon.name}</strong> ({merchant.weapon.type}, 예리도 {merchant.weapon.sharpness}, 희귀도 {merchant.weapon.rarity}) — {merchant.weapon.asking_price} 골드</li>
        )}
      </ul>

      <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
        <button className="btn" onClick={() => setEntering(true)} disabled={busy}>협상하기</button>
        <button className="btn" onClick={skip} disabled={busy}>건너뛰기</button>
      </div>
      {err && <p style={{ color: "red" }}>{err}</p>}
    </div>
  );
}
```

- [ ] **Step 2: `frontend/src/components/MerchantNegotiation.tsx`**

```typescript
import { useState } from "react";
import { api } from "../api";
import type { MerchantToday, NegotiateResponse } from "../types";

interface ChatMsg { role: "player" | "merchant"; message: string; price?: number | null }

export function MerchantNegotiation({ merchant, onDone }: { merchant: MerchantToday; onDone: () => void }) {
  const baseTotal = merchant.materials.reduce((s, m) => s + m.asking_price, 0)
                  + (merchant.weapon?.asking_price ?? 0);

  const [msgs, setMsgs] = useState<ChatMsg[]>([
    { role: "merchant", message: `이 묶음 ${baseTotal} 골드는 어떻소?`, price: baseTotal },
  ]);
  const [price, setPrice] = useState<number>(Math.floor(baseTotal * 0.7));
  const [text, setText] = useState<string>("");
  const [last, setLast] = useState<NegotiateResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const send = async () => {
    setBusy(true); setErr(null);
    try {
      const res = await api.merchantNegotiate(merchant.id, price, text, last?.negotiation_id ?? null);
      setMsgs((m) => [...m,
        { role: "player", message: text, price },
        { role: "merchant", message: res.message, price: res.counter_price }]);
      setLast(res);
      setText("");
      if (res.counter_price) setPrice(res.counter_price);
    } catch (e: unknown) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  const finalize = async () => {
    if (!last) return;
    setBusy(true);
    try { await api.merchantFinalize(last.negotiation_id); onDone(); }
    catch (e: unknown) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  const acceptCounter = async () => {
    if (!last) return;
    setBusy(true);
    try { await api.merchantPlayerAccept(last.negotiation_id); onDone(); }
    catch (e: unknown) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  const reject = async () => {
    if (!last) return;
    setBusy(true);
    try { await api.merchantPlayerReject(last.negotiation_id); onDone(); }
    catch (e: unknown) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  return (
    <div>
      <h2>상인 협상</h2>
      <p>묶음 시세: {baseTotal} 골드</p>

      <div className="chat">
        {msgs.map((m, i) => (
          <div key={i} className={`msg ${m.role === "player" ? "player" : "hero"}`}>
            <strong>{m.role === "player" ? "나" : "상인"}:</strong> {m.message}
            {m.price != null && <em> ({m.price} 골드)</em>}
          </div>
        ))}
      </div>

      {last?.decision === "accept" ? (
        <div style={{ marginTop: 16 }}>
          <p>상인이 수락했습니다.</p>
          <button className="btn" onClick={finalize} disabled={busy}>확정</button>
        </div>
      ) : last?.decision === "reject" ? (
        <div style={{ marginTop: 16 }}>
          <p>협상이 결렬되었습니다.</p>
          <button className="btn" onClick={onDone}>다음으로</button>
        </div>
      ) : (
        <div style={{ marginTop: 16 }}>
          {last?.decision === "counter" && last.counter_price != null && (
            <div style={{ marginBottom: 12, padding: 8, background: "#fff4d6", borderRadius: 6 }}>
              <p style={{ margin: "0 0 8px" }}>상인이 <strong>{last.counter_price} 골드</strong>를 역제안했습니다.</p>
              <button className="btn" onClick={acceptCounter} disabled={busy} style={{ marginRight: 8 }}>
                {last.counter_price} 골드에 수락
              </button>
              <button className="btn" onClick={reject} disabled={busy}>거절하고 떠나기</button>
            </div>
          )}
          <div>
            <label>제시 가격:
              <input type="number" value={price} onChange={(e) => setPrice(Number(e.target.value))} />
            </label>
          </div>
          <textarea rows={3} style={{ width: "100%" }} value={text} onChange={(e) => setText(e.target.value)} placeholder="상인에게 한마디" />
          <button className="btn" onClick={send} disabled={busy || !text.trim()}>{busy ? "..." : "제안하기"}</button>
        </div>
      )}
      {err && <p style={{ color: "red" }}>{err}</p>}
    </div>
  );
}
```

- [ ] **Step 3: 타입체크**

```bash
cd /home/afraidnot/dev/smith-tycoon/frontend && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add frontend/src/components/MerchantPanel.tsx frontend/src/components/MerchantNegotiation.tsx && git commit -m "feat(frontend): MerchantPanel and MerchantNegotiation chat UI"
```

---

## Task 17: DaySummary + GameOver 컴포넌트

**Files:**
- Create: `frontend/src/components/DaySummary.tsx`
- Create: `frontend/src/components/GameOver.tsx`

- [ ] **Step 1: `frontend/src/components/DaySummary.tsx`**

```typescript
import { useEffect, useState } from "react";
import { api } from "../api";
import type { DaySummaryResponse } from "../types";

export function DaySummary({ onDone }: { onDone: () => void }) {
  const [data, setData] = useState<DaySummaryResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.daySummary().then(setData).catch((e) => setErr(e.message));
  }, []);

  const next = async () => {
    setBusy(true);
    try { await api.nextDay(); onDone(); }
    catch (e: unknown) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  if (err) return <p style={{ color: "red" }}>요약 로드 실패: {err}</p>;
  if (!data) return <p>요약 준비 중...</p>;

  const s = data.summary;
  return (
    <div>
      <h2>Day {data.day} 요약</h2>
      <ul>
        <li>제작: {s.forges}건</li>
        <li>판매: {s.sales}건, 골드 변화 {s.gold_delta >= 0 ? "+" : ""}{s.gold_delta}</li>
        <li>구매: {s.buys}건</li>
        <li>전투: {s.battles}건 (생존 {s.heroes_survived} / 부상 {s.heroes_injured} / 사망 {s.heroes_died})</li>
        <li>평판 변화: {s.rep_delta >= 0 ? "+" : ""}{s.rep_delta}</li>
      </ul>

      <h4>이벤트 로그</h4>
      <ul style={{ maxHeight: 240, overflowY: "auto", border: "1px solid #ccc", padding: 8 }}>
        {data.events.map((e) => (
          <li key={e.id}><code>{e.kind}</code>: {JSON.stringify(e.payload)}</li>
        ))}
      </ul>

      <button className="btn" onClick={next} disabled={busy} style={{ marginTop: 16 }}>
        {busy ? "..." : "다음 날"}
      </button>
    </div>
  );
}
```

- [ ] **Step 2: `frontend/src/components/GameOver.tsx`**

```typescript
import { useState } from "react";
import { api } from "../api";

export function GameOver({ onReset }: { onReset: () => void }) {
  const [busy, setBusy] = useState(false);
  const reset = async () => {
    setBusy(true);
    try { await api.resetGame(); onReset(); }
    finally { setBusy(false); }
  };
  return (
    <div>
      <h2>5일 운영 종료</h2>
      <p>대장간 5일 운영이 마무리되었습니다. 새 게임을 시작하시겠어요?</p>
      <button className="btn" onClick={reset} disabled={busy}>새 게임</button>
    </div>
  );
}
```

- [ ] **Step 3: 타입체크**

```bash
cd /home/afraidnot/dev/smith-tycoon/frontend && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add frontend/src/components/DaySummary.tsx frontend/src/components/GameOver.tsx && git commit -m "feat(frontend): DaySummary and GameOver components"
```

---

## Task 18: DayRouter 갱신 — 10+1 phase 라우팅

**Files:**
- Modify: `frontend/src/components/DayRouter.tsx`

- [ ] **Step 1: `frontend/src/components/DayRouter.tsx` 전체 교체**

```typescript
import type { StateResponse } from "../types";
import { ForgePanel } from "./ForgePanel";
import { NegotiationChat } from "./NegotiationChat";
import { BattleResult } from "./BattleResult";
import { MerchantPanel } from "./MerchantPanel";
import { DaySummary } from "./DaySummary";
import { GameOver } from "./GameOver";

const NEGOTIATE_PHASES = new Set(["hero1_negotiate", "hero2_negotiate", "hero3_negotiate"]);
const BATTLE_PHASES = new Set(["hero1_battle", "hero2_battle", "hero3_battle"]);
const FORGE_PHASES = new Set(["forge_open", "forge_open_2"]);

export function DayRouter({ state, refresh, onReset }: { state: StateResponse; refresh: () => void; onReset: () => void }) {
  if (!state.player) return null;
  const phase = state.player.current_phase;

  if (FORGE_PHASES.has(phase)) {
    return <ForgePanel inventory={state.inventory} onDone={refresh} />;
  }
  if (NEGOTIATE_PHASES.has(phase)) {
    if (!state.hero || state.weapons.length === 0) {
      // 무기가 없으면 협상 불가 — 자동 진행 안 함. forge로 돌아갔거나 진열장 비었음.
      return <p>판매할 무기가 없습니다. (제작을 건너뛰셨다면 이번 협상은 무기 없이 진행됩니다.)</p>;
    }
    return <NegotiationChat hero={state.hero} weapon={state.weapons[0]} onDone={refresh} />;
  }
  if (BATTLE_PHASES.has(phase)) {
    return <BattleResult onDone={refresh} />;
  }
  if (phase === "merchant_negotiate") {
    if (!state.merchant) return <p>상인 정보를 불러오는 중...</p>;
    return <MerchantPanel merchant={state.merchant} onDone={refresh} />;
  }
  if (phase === "day_summary") {
    return <DaySummary onDone={refresh} />;
  }
  if (phase === "game_over") {
    return <GameOver onReset={onReset} />;
  }
  return <p>알 수 없는 phase: {phase}</p>;
}
```

- [ ] **Step 2: `frontend/src/App.tsx` — onReset 전달**

App.tsx 상단 import는 그대로 두고, `<DayRouter ... />` 호출에 `onReset={reset}` 추가:

```typescript
import { useEffect, useState } from "react";
import { api } from "./api";
import type { StateResponse } from "./types";
import { SidePanel } from "./components/SidePanel";
import { DayRouter } from "./components/DayRouter";

export default function App() {
  const [state, setState] = useState<StateResponse | null>(null);

  const refresh = async () => setState(await api.getState());
  const reset = async () => { await api.resetGame(); await refresh(); };

  useEffect(() => { refresh().catch(() => setState(null)); }, []);

  if (!state || !state.player) {
    return (
      <div style={{ padding: 24 }}>
        <button className="btn" onClick={reset}>새 게임 시작</button>
      </div>
    );
  }

  return (
    <div className="app">
      <SidePanel state={state} onReset={reset} />
      <div className="main">
        <DayRouter state={state} refresh={refresh} onReset={reset} />
      </div>
    </div>
  );
}
```

- [ ] **Step 3: 타입체크**

```bash
cd /home/afraidnot/dev/smith-tycoon/frontend && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add frontend/src/components/DayRouter.tsx frontend/src/App.tsx && git commit -m "feat(frontend): DayRouter for all Plan 2 phases + App onReset wiring"
```

---

## Task 19: 수동 검증 체크리스트 문서

**Files:**
- Create: `docs/superpowers/plans/2026-05-26-mvp-plan2-checklist.md`

- [ ] **Step 1: 체크리스트 문서 작성**

`docs/superpowers/plans/2026-05-26-mvp-plan2-checklist.md`:

```markdown
# Plan 2 수동 검증 체크리스트

## 사전
- [ ] Supabase에 `backend/migrations/002_daily_loop.sql` 실행 (MCP `apply_migration` 또는 SQL Editor)
- [ ] 신규 테이블 2개 (`merchants_today`, `day_events`) 존재
- [ ] `heroes.held_weapon_id` 컬럼 존재
- [ ] 9개 테이블 RLS 활성·`materials_anon_read` 정책 존재
- [ ] uvicorn + vite 동작

## 5일 골든 패스 (실제 LLM)
- [ ] 새 게임 시작 → Day 1 / 5 표시
- [ ] forge_open 제작 또는 skip 동작
- [ ] hero1 협상 → 전투
- [ ] 상인 협상 (counter → accept) → 인벤토리에 재료·무기 추가, 금화 차감
- [ ] hero2 협상 → 전투
- [ ] forge_open_2 제작 또는 skip
- [ ] hero3 협상 → 전투
- [ ] day_summary — 이벤트 리스트·요약 통계 표시
- [ ] "다음 날" → Day 2 forge_open
- [ ] Day 2에서 Day 1 생존 용사가 재방문하는지 (return_day=4 였다면 안 나옴, return_day=3이면 나옴)
- [ ] Day 5 day_summary 후 "다음 날" → GameOver 화면

## 전투 강화 검증
- [ ] Day 1에서 맨손 전투 시 부상·사망 빈도 증가 (체감)
- [ ] Day 5에서 demon 난이도 20+ 등장, 강한 무기 없이 이기기 어려움

## 상인 협상
- [ ] 묶음 시세 표시 합리적
- [ ] counter / accept / reject 분기 모두 동작
- [ ] 즉시 거절 시 평판 변화 없음, 협상 후 거절 시 -1

## RLS 검증
- [ ] anon 키로 `players` SELECT → 0 rows
- [ ] anon 키로 `materials` SELECT → 20 rows
- [ ] 백엔드는 service_role 사용해 정상 동작

## LLM 비용
- [ ] `GET /llm/usage` 호출해 5일 풀 플레이 누적 USD 확인
- [ ] 한 일차당 LLM 호출 ~10번 예상 (forge 2, 협상 3-9, 전투 3)

## 미포함
- 자동 회귀 테스트 (백엔드 pytest는 유지하되 5일 시뮬레이션은 수동)
- 호감도 효과 (Plan 3)
- 강화 협상 (Plan 3)
```

- [ ] **Step 2: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add docs/superpowers/plans/2026-05-26-mvp-plan2-checklist.md && git commit -m "docs: Plan 2 manual verification checklist"
```

---

## 완료 조건 (Definition of Done)

- 모든 backend pytest PASS (총 30+ 테스트 예상)
- `tsc --noEmit` 오류 없음
- 002 마이그레이션 Supabase 적용 완료
- 5일 골든 패스 수동 검증 통과
- 체크리스트의 RLS·LLM 비용 항목 확인
- 모든 커밋 main 또는 feature 브랜치에 push

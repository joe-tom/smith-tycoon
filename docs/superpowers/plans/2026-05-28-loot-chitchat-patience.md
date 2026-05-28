# 전리품 · chitchat · 인내심 — 구현 계획 (2차 배치)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 메뉴식 hero visitor 패널 위에 전리품 매수 협상, chitchat(lore 저장), 인내심 스탯을 얹는다.

**Architecture:** 1차의 returning_hero 슬롯을 메뉴 모드로 확장. 전리품은 dispatch 시점에 보스 시그니처 + 난이도 풀로 굴려 `heroes.loot_pending`에 저장. 인내심은 협상 시작 시 페르소나/시드로 계산해 `negotiations.patience_start`에 박고 라운드별로 감소시켜 0이면 자동 종료. chitchat은 affinity ≥ 0 게이트, LLM 한 문단 narration을 `heroes.lore` JSONB에 누적.

**Tech Stack:** Python 3.12 + FastAPI + Supabase (Postgres) + Pytest, React 18 + TypeScript + Vite.

**Spec:** `docs/superpowers/specs/2026-05-28-loot-chitchat-patience-design.md`

---

## File Structure

**Backend — create**
- `backend/migrations/011_loot_chitchat_patience.sql`
- `backend/app/patience.py` — 시작값 계산 + 라운드 감소 + 임계 판정
- `backend/app/loot_table.py` — drop pool
- `backend/app/chitchat.py` — chitchat 서비스 (LLM 호출 + lore append)
- `backend/app/api/loot.py` — `/loot/*` 엔드포인트
- `backend/app/api/chitchat.py` — `/visitor/current/chitchat`
- `backend/app/llm/prompts/chitchat.j2`
- `backend/tests/fixtures/llm/chitchat.json`
- `backend/tests/test_patience.py`
- `backend/tests/test_loot_table.py`
- `backend/tests/test_chitchat.py`
- `backend/tests/test_step_buy_loot.py`
- `backend/tests/test_dispatch_loot_integration.py`

**Backend — modify**
- `backend/app/repo.py` — list_materials_by_category, update_hero_lore, append_hero_loot, finalize loot helpers, update_negotiation patience 필드
- `backend/app/combat.py` (`dispatch_async_battle`) — loot roll
- `backend/app/negotiation.py` — step_sell/step_buy에 인내심 적용 + 자동 종료; step_buy_loot + finalize_buy_loot 추가
- `backend/app/api/state.py` — hero 슬롯 hydrate에 lore/loot_pending/negotiation patience 포함
- `backend/app/main.py` — loot/chitchat 라우터 등록
- `backend/tests/fake_repo.py` — 신규 메서드들

**Frontend — create**
- `frontend/src/components/HeroVisitorPanel.tsx` — 메뉴 + 인라인 sub-state
- `frontend/src/components/LootNegotiation.tsx`
- `frontend/src/components/ChitchatPanel.tsx`
- `frontend/src/components/PatienceGauge.tsx`

**Frontend — modify**
- `frontend/src/types.ts`
- `frontend/src/api.ts`
- `frontend/src/components/VisitorRouter.tsx` — hero kind → HeroVisitorPanel로 일원화
- `frontend/src/components/NegotiationChat.tsx` — PatienceGauge 마운트 + patience exhausted 처리
- `frontend/src/components/MerchantPanel.tsx` — 동일
- `frontend/src/components/EnhanceNegotiation.tsx` — 동일

**Frontend — delete**
- `frontend/src/components/ReturningHeroPanel.tsx`

---

### Task 1: 마이그레이션 011

**Files:**
- Create: `backend/migrations/011_loot_chitchat_patience.sql`

- [ ] **Step 1: 마이그레이션 SQL 작성**

```sql
-- 011_loot_chitchat_patience.sql
ALTER TABLE heroes
  ADD COLUMN IF NOT EXISTS lore JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS loot_pending JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE negotiations
  ADD COLUMN IF NOT EXISTS patience_start INT,
  ADD COLUMN IF NOT EXISTS patience_current INT;
```

- [ ] **Step 2: Supabase 적용 + 커밋**

사용자에게 안내: MCP `apply_migration` 또는 Studio SQL Editor로 적용.

```bash
git add backend/migrations/011_loot_chitchat_patience.sql
git commit -m "migrate: 011 add heroes.lore/loot_pending + negotiations.patience_*"
```

---

### Task 2: FakeRepo 확장

**Files:**
- Modify: `backend/tests/fake_repo.py`

- [ ] **Step 1: FakeRepo에 메서드 추가**

```python
# FakeRepo.__init__ 에 추가
self.materials: list[dict] = []   # [{id, name, category, attribute, base_price}]
self.negotiations: list[dict] = []
self._neg_seq = 0
self.inventory: dict[int, list[dict]] = {}  # player_id -> [{material_id, qty, ...}]

# 메서드 추가:
def list_materials_by_category(self, category: str) -> list[dict]:
    return [m for m in self.materials if m["category"] == category]

def update_hero(self, hero_id: int, **fields):
    for h in self.heroes:
        if h["id"] == hero_id:
            h.update(fields)
            return

def append_hero_lore(self, hero_id: int, entry: dict, cap: int = 20):
    h = self.get_hero(hero_id)
    if h is None: return
    lore = list(h.get("lore") or [])
    lore.append(entry)
    if len(lore) > cap:
        lore = lore[-cap:]
    h["lore"] = lore

def append_hero_loot(self, hero_id: int, items: list[dict]):
    h = self.get_hero(hero_id)
    if h is None: return
    h["loot_pending"] = list(h.get("loot_pending") or []) + items

def clear_hero_loot(self, hero_id: int):
    h = self.get_hero(hero_id)
    if h: h["loot_pending"] = []

def insert_negotiation(self, player_id: int, neg: dict) -> dict:
    self._neg_seq += 1
    saved = {"id": self._neg_seq, "player_id": player_id, **neg}
    self.negotiations.append(saved)
    return saved

def get_negotiation(self, neg_id: int):
    return next((n for n in self.negotiations if n["id"] == neg_id), None)

def update_negotiation(self, neg_id: int, **fields):
    n = self.get_negotiation(neg_id)
    if n: n.update(fields)

def add_inventory(self, player_id: int, material_id: int, qty: int):
    rows = self.inventory.setdefault(player_id, [])
    for r in rows:
        if r["material_id"] == material_id:
            r["qty"] += qty
            return
    mat = next((m for m in self.materials if m["id"] == material_id), {})
    rows.append({"material_id": material_id, "qty": qty,
                 "name": mat.get("name", "?"), "category": mat.get("category", "?"),
                 "attribute": mat.get("attribute"), "base_price": mat.get("base_price", 0)})
```

- [ ] **Step 2: Run baseline tests**

```bash
cd backend && source .venv/bin/activate && python -m pytest -q
```
Expected: 179 passed.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/fake_repo.py
git commit -m "test: extend FakeRepo with materials, negotiations, hero lore/loot helpers"
```

---

### Task 3: repo.py 확장

**Files:**
- Modify: `backend/app/repo.py`

- [ ] **Step 1: 함수 추가 (파일 끝에 append)**

```python
# --- 011: lore / loot / materials ---

def list_materials_by_category(category: str) -> list[dict[str, Any]]:
    return _client().table("materials").select("*").eq("category", category).execute().data


def append_hero_lore(hero_id: int, entry: dict[str, Any], cap: int = 20) -> None:
    hero = get_hero(hero_id)
    if not hero:
        return
    lore = list(hero.get("lore") or [])
    lore.append(entry)
    if len(lore) > cap:
        lore = lore[-cap:]
    _client().table("heroes").update({"lore": lore}).eq("id", hero_id).execute()


def append_hero_loot(hero_id: int, items: list[dict[str, Any]]) -> None:
    hero = get_hero(hero_id)
    if not hero:
        return
    existing = list(hero.get("loot_pending") or [])
    _client().table("heroes").update({"loot_pending": existing + items}) \
        .eq("id", hero_id).execute()


def clear_hero_loot(hero_id: int) -> None:
    _client().table("heroes").update({"loot_pending": []}).eq("id", hero_id).execute()
```

- [ ] **Step 2: 모듈 임포트 확인**

```bash
source .venv/bin/activate && python -c "from app import repo; print(repo.list_materials_by_category, repo.append_hero_lore)"
```
Expected: 함수 참조 두 개 출력.

- [ ] **Step 3: Commit**

```bash
git add backend/app/repo.py
git commit -m "repo: add list_materials_by_category + hero lore/loot helpers"
```

---

### Task 4: patience.py 모듈

**Files:**
- Create: `backend/app/patience.py`
- Create: `backend/tests/test_patience.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# backend/tests/test_patience.py
import pytest
from app import patience


def test_hero_start_value_호탕():
    hero = {"personality_tags": ["호탕"]}
    assert patience.hero_start(hero) == 70


def test_hero_start_value_깐깐_소심():
    hero = {"personality_tags": ["깐깐", "소심"]}
    # base 50 - 20 - 10 = 20
    assert patience.hero_start(hero) == 20


def test_hero_start_value_clamped_low():
    hero = {"personality_tags": ["깐깐", "깐깐", "깐깐"]}  # 50 - 60 = -10 → clamp 10
    assert patience.hero_start(hero) == 10


def test_hero_start_value_clamped_high():
    hero = {"personality_tags": ["호탕", "호탕", "호탕"]}  # 50 + 60 = 110 → clamp 90
    assert patience.hero_start(hero) == 90


def test_hero_start_value_unknown_tag_ignored():
    hero = {"personality_tags": ["호탕", "알수없음"]}
    assert patience.hero_start(hero) == 70


def test_merchant_start_value_range():
    seeds_to_results = {patience.merchant_start(player_id=1, day=d, merchant_id=1) for d in range(50)}
    assert all(30 <= v <= 70 for v in seeds_to_results)


def test_merchant_start_value_deterministic():
    assert patience.merchant_start(1, 5, 7) == patience.merchant_start(1, 5, 7)


def test_decrement_normal():
    assert patience.next_after_round(50, conceded=False) == 40


def test_decrement_with_concession():
    assert patience.next_after_round(50, conceded=True) == 45


def test_level_thresholds():
    assert patience.level(80) == "high"
    assert patience.level(31) == "high"
    assert patience.level(30) == "low"
    assert patience.level(1) == "low"
    assert patience.level(0) == "exhausted"
    assert patience.level(-5) == "exhausted"


def test_exhausted():
    assert patience.is_exhausted(0)
    assert patience.is_exhausted(-1)
    assert not patience.is_exhausted(1)
```

- [ ] **Step 2: Run — should fail (module missing)**

```bash
source .venv/bin/activate && python -m pytest tests/test_patience.py -v
```
Expected: ImportError.

- [ ] **Step 3: 구현**

```python
# backend/app/patience.py
"""협상 인내심 — 시작값 계산, 라운드 감소, 임계값 판정."""
from __future__ import annotations
import random

PERSONA_DELTAS = {
    "호탕": 20, "깐깐": -20, "검소": 0, "소심": -10, "허세": -10,
}
BASE = 50
HERO_FLOOR = 10
HERO_CEIL = 90


def hero_start(hero: dict) -> int:
    delta = sum(PERSONA_DELTAS.get(tag, 0) for tag in (hero.get("personality_tags") or []))
    return max(HERO_FLOOR, min(HERO_CEIL, BASE + delta))


def merchant_start(player_id: int, day: int, merchant_id: int) -> int:
    seed = (player_id * 1_000_003 + day * 31 + merchant_id * 7 + 19) & 0xFFFFFFFF
    return random.Random(seed).randint(30, 70)


def next_after_round(current: int, conceded: bool) -> int:
    return current - (5 if conceded else 10)


def level(current: int) -> str:
    if current <= 0:
        return "exhausted"
    if current <= 30:
        return "low"
    return "high"


def is_exhausted(current: int) -> bool:
    return current <= 0
```

- [ ] **Step 4: Run — should pass**

Run: `python -m pytest tests/test_patience.py -v`
Expected: PASS (모두).

- [ ] **Step 5: Commit**

```bash
git add backend/app/patience.py backend/tests/test_patience.py
git commit -m "feat(patience): persona/seed-based start, per-round decrement, threshold levels"
```

---

### Task 5: loot_table.py + 테스트

**Files:**
- Create: `backend/app/loot_table.py`
- Create: `backend/tests/test_loot_table.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# backend/tests/test_loot_table.py
from unittest.mock import patch
from app import loot_table


def _demon(difficulty=3, is_boss=False, boss_id=None, **kw):
    return {"difficulty": difficulty, "is_boss": is_boss, "boss_id": boss_id, **kw}


def _make_materials():
    return [
        {"id": 1, "category": "일반", "name": "철"},
        {"id": 2, "category": "일반", "name": "원목"},
        {"id": 3, "category": "일반", "name": "가죽"},
        {"id": 4, "category": "이상한", "name": "녹슨못"},
        {"id": 5, "category": "이상한", "name": "버려진끈"},
        {"id": 6, "category": "특수", "name": "마정석"},
        {"id": 7, "category": "전설", "name": "화염정수"},
    ]


def _stub_repo(materials):
    class R:
        def list_materials_by_category(self, cat):
            return [m for m in materials if m["category"] == cat]
    return R()


@patch("app.loot_table.repo")
def test_roll_loot_low_difficulty_common_only(mock_repo):
    mats = _make_materials()
    mock_repo.list_materials_by_category.side_effect = _stub_repo(mats).list_materials_by_category
    loot = loot_table.roll_loot(_demon(difficulty=2), seed=42)
    cats = {next(m for m in mats if m["id"] == it["material_id"])["category"] for it in loot}
    assert cats == {"일반"}
    assert 1 <= len(loot) <= 2


@patch("app.loot_table.repo")
def test_roll_loot_mid_difficulty_uncommon_possible(mock_repo):
    mats = _make_materials()
    mock_repo.list_materials_by_category.side_effect = _stub_repo(mats).list_materials_by_category
    seen_uncommon = False
    for s in range(50):
        loot = loot_table.roll_loot(_demon(difficulty=5), seed=s)
        cats = {next(m for m in mats if m["id"] == it["material_id"])["category"] for it in loot}
        if "이상한" in cats:
            seen_uncommon = True
            break
    assert seen_uncommon


@patch("app.loot_table.repo")
def test_roll_loot_high_difficulty_rare_possible(mock_repo):
    mats = _make_materials()
    mock_repo.list_materials_by_category.side_effect = _stub_repo(mats).list_materials_by_category
    seen_rare = False
    for s in range(50):
        loot = loot_table.roll_loot(_demon(difficulty=8), seed=s)
        cats = {next(m for m in mats if m["id"] == it["material_id"])["category"] for it in loot}
        if "특수" in cats:
            seen_rare = True
            break
    assert seen_rare


@patch("app.loot_table.repo")
def test_roll_loot_boss_signature(mock_repo):
    mats = _make_materials()
    mock_repo.list_materials_by_category.side_effect = _stub_repo(mats).list_materials_by_category
    loot = loot_table.roll_loot(_demon(difficulty=10, is_boss=True, boss_id="surt"), seed=1)
    names = {next(m for m in mats if m["id"] == it["material_id"])["name"] for it in loot}
    assert "화염정수" in names


@patch("app.loot_table.repo")
def test_roll_loot_deterministic(mock_repo):
    mats = _make_materials()
    mock_repo.list_materials_by_category.side_effect = _stub_repo(mats).list_materials_by_category
    a = loot_table.roll_loot(_demon(difficulty=5), seed=99)
    b = loot_table.roll_loot(_demon(difficulty=5), seed=99)
    assert a == b


@patch("app.loot_table.repo")
def test_roll_loot_empty_category_returns_no_item(mock_repo):
    # 일반 카테고리가 비면 일반 슬롯도 비어야 한다 (크래시 금지)
    mock_repo.list_materials_by_category.side_effect = lambda cat: []
    loot = loot_table.roll_loot(_demon(difficulty=3), seed=1)
    assert loot == []
```

- [ ] **Step 2: Run — should fail**

```bash
python -m pytest tests/test_loot_table.py -v
```
Expected: ImportError.

- [ ] **Step 3: 구현**

```python
# backend/app/loot_table.py
"""몹 → 전리품 드롭. 결정성 시드."""
from __future__ import annotations
import random
from typing import Any
from . import repo

BOSS_LOOT: dict[str, list[dict[str, Any]]] = {
    "surt": [{"category": "전설", "name_hint": "화염정수", "qty": 1}],
}


def _pick_from_category(category: str, rng: random.Random, n: int) -> list[dict[str, Any]]:
    pool = repo.list_materials_by_category(category)
    if not pool:
        return []
    out = []
    for _ in range(n):
        m = rng.choice(pool)
        out.append({"material_id": m["id"], "qty": 1})
    return out


def _pick_matching(category: str, name_hint: str, rng: random.Random) -> dict[str, Any] | None:
    pool = repo.list_materials_by_category(category)
    matching = [m for m in pool if name_hint in (m.get("name") or "")]
    chosen = matching[0] if matching else (rng.choice(pool) if pool else None)
    return {"material_id": chosen["id"], "qty": 1} if chosen else None


def roll_loot(demon: dict[str, Any], seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    out: list[dict[str, Any]] = []
    difficulty = int(demon.get("difficulty", 1))

    if demon.get("is_boss") and demon.get("boss_id") in BOSS_LOOT:
        for tmpl in BOSS_LOOT[demon["boss_id"]]:
            picked = _pick_matching(tmpl["category"], tmpl.get("name_hint", ""), rng)
            if picked:
                picked["qty"] = tmpl["qty"]
                out.append(picked)
        out.extend(_pick_from_category("일반", rng, rng.randint(2, 3)))
        return out

    if difficulty <= 3:
        out.extend(_pick_from_category("일반", rng, rng.randint(1, 2)))
    elif difficulty <= 6:
        out.extend(_pick_from_category("일반", rng, rng.randint(2, 3)))
        if rng.random() < 0.3:
            out.extend(_pick_from_category("이상한", rng, 1))
    else:  # 7-9
        out.extend(_pick_from_category("일반", rng, rng.randint(2, 3)))
        if rng.random() < 0.4:
            out.extend(_pick_from_category("특수", rng, 1))

    return out
```

- [ ] **Step 4: Run — should pass**

```bash
python -m pytest tests/test_loot_table.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/loot_table.py backend/tests/test_loot_table.py
git commit -m "feat(loot-table): hybrid boss signature + difficulty-bracketed pool"
```

---

### Task 6: dispatch_async_battle에 loot 통합

**Files:**
- Modify: `backend/app/combat.py`
- Create: `backend/tests/test_dispatch_loot_integration.py`

- [ ] **Step 1: 실패 테스트**

```python
# backend/tests/test_dispatch_loot_integration.py
from unittest.mock import patch, MagicMock
import pytest
from app import combat


@pytest.mark.asyncio
async def test_dispatch_adds_loot_on_survive_kill(fake_repo, monkeypatch):
    # heroes / weapons / materials 준비
    fake_repo.heroes.append({"id": 1, "player_id": 1, "name": "H", "str": 5, "mag": 5,
                              "level": 1, "personality_tags": [], "affinity": 0,
                              "history": [], "loot_pending": [], "lore": [],
                              "status": "alive"})
    fake_repo.weapons.append({"id": 10, "player_id": 1, "name": "검", "attack": 10,
                               "sharpness": 30, "attribute": "화", "type": "검",
                               "owner": "player", "rarity": 0,
                               "materials_used": [{"category": "일반"}]})
    fake_repo.materials = [
        {"id": 100, "category": "일반", "name": "철", "base_price": 50},
    ]
    fake_repo.players[1] = {"id": 1, "current_day": 1, "current_phase": "visitor",
                             "reputation": 0, "heroes_died_total": 0,
                             "weapons_destroyed_total": 0}

    monkeypatch.setattr(combat, "repo", fake_repo)
    from app import pending_outcomes as po, loot_table, scheduler, hero_registry, \
        nickname as nickname_mod, affinity as affinity_mod, endgame
    monkeypatch.setattr(po, "repo", fake_repo)
    monkeypatch.setattr(loot_table, "repo", fake_repo)

    # 강한 영웅 + 약한 적 → survive+killed 강제
    monkeypatch.setattr(combat, "roll_demon",
                        lambda day, defeated_boss_ids=None: {
                            "id": "imp", "name": "임프", "difficulty": 1, "attribute": "수",
                            "type": "imp"
                        })
    # 결과를 강제로 survive/killed로 패치
    monkeypatch.setattr(combat, "decide_outcomes",
                        lambda h, w, d, seed=None: {
                            "hero": "survived", "weapon": "preserved", "demon": "killed",
                            "hero_opinion": "none"
                        })

    player = fake_repo.players[1]
    result = await combat.dispatch_async_battle(player, hero_id=1, weapon_id=10)

    h = fake_repo.get_hero(1)
    assert len(h["loot_pending"]) >= 1, "전리품이 채워져야 함"
    # outcome_json 에 loot 사본
    pending = fake_repo.pending_outcomes[-1]
    assert "loot" in pending["outcome_json"]


@pytest.mark.asyncio
async def test_dispatch_no_loot_on_die(fake_repo, monkeypatch):
    fake_repo.heroes.append({"id": 1, "player_id": 1, "name": "H", "str": 5, "mag": 5,
                              "level": 1, "personality_tags": [], "affinity": 0,
                              "history": [], "loot_pending": [], "lore": [],
                              "status": "alive"})
    fake_repo.weapons.append({"id": 10, "player_id": 1, "name": "검", "attack": 10,
                               "sharpness": 30, "attribute": "화", "type": "검",
                               "owner": "player", "rarity": 0,
                               "materials_used": [{"category": "일반"}]})
    fake_repo.materials = [{"id": 100, "category": "일반", "name": "철", "base_price": 50}]
    fake_repo.players[1] = {"id": 1, "current_day": 1, "current_phase": "visitor",
                             "reputation": 0, "heroes_died_total": 0,
                             "weapons_destroyed_total": 0}

    monkeypatch.setattr(combat, "repo", fake_repo)
    from app import pending_outcomes as po, loot_table
    monkeypatch.setattr(po, "repo", fake_repo)
    monkeypatch.setattr(loot_table, "repo", fake_repo)
    monkeypatch.setattr(combat, "roll_demon",
                        lambda day, defeated_boss_ids=None: {
                            "id": "imp", "name": "임프", "difficulty": 1, "attribute": "수",
                            "type": "imp"
                        })
    monkeypatch.setattr(combat, "decide_outcomes",
                        lambda h, w, d, seed=None: {
                            "hero": "died", "weapon": "destroyed", "demon": "survived",
                            "hero_opinion": "weapon_broke"
                        })

    await combat.dispatch_async_battle(fake_repo.players[1], hero_id=1, weapon_id=10)
    h = fake_repo.get_hero(1)
    assert h["loot_pending"] == [], "사망 시 전리품 없어야 함"
```

- [ ] **Step 2: combat.dispatch_async_battle 수정**

`backend/app/combat.py`에서 dispatch_async_battle 내부, outcome 결정 직후·pending insert 직전에 loot 처리 추가:

```python
# decide_outcomes 호출 후, pending insert 전에:
from . import loot_table as _lt
loot: list[dict[str, Any]] = []
if outcomes["hero"] != "died" and outcomes["demon"] == "killed":
    loot = _lt.roll_loot(demon, seed=seed + 17)
    if loot:
        repo.append_hero_loot(hero_id, loot)

# outcome_json 에 loot 포함하도록 변경:
saved = repo.insert_pending_outcome({
    "player_id": pid,
    "hero_id": hero_id,
    "depart_day": player["current_day"],
    "resolve_day": resolve_day,
    "kind": kind,
    "outcome_json": {**outcomes, "demon": demon,
                     "monsters_killed": 1 if outcomes["demon"] == "killed" else 0,
                     "loot": loot},
    "weapon_snapshot": weapon_snapshot,
})
```

(기존의 outcome_json 박는 곳을 위 형태로 교체.)

- [ ] **Step 3: Run**

```bash
python -m pytest tests/test_dispatch_loot_integration.py -v
```
Expected: PASS (둘 다).

- [ ] **Step 4: 기존 회귀**

```bash
python -m pytest -q
```
Expected: 모두 통과 (추가된 loot 키는 기존 테스트가 무시).

- [ ] **Step 5: Commit**

```bash
git add backend/app/combat.py backend/tests/test_dispatch_loot_integration.py
git commit -m "feat(combat): roll loot on dispatch and append to hero.loot_pending"
```

---

### Task 7: 인내심 — negotiation.step_sell/step_buy 통합

**Files:**
- Modify: `backend/app/negotiation.py`
- Modify: `backend/tests/test_negotiation.py` (인내심 케이스 추가)

- [ ] **Step 1: 실패 테스트 추가**

`backend/tests/test_negotiation.py` 끝에 append:

```python
import pytest
from unittest.mock import patch
from app import negotiation


@pytest.mark.asyncio
async def test_step_sell_initializes_patience(fake_repo, monkeypatch):
    fake_repo.heroes.append({
        "id": 1, "player_id": 1, "name": "H", "job": "검사",
        "str": 5, "mag": 5, "personality_tags": ["깐깐"],
        "affinity": 0, "history": [], "gold": 1000,
    })
    fake_repo.weapons.append({
        "id": 10, "player_id": 1, "owner": "player", "name": "검", "type": "검",
        "rarity": 0, "sharpness": 30, "materials_used": [{"category": "일반"}],
        "attribute": "화",
    })
    fake_repo.materials = [{"id": 1, "category": "일반", "base_price": 50}]
    fake_repo.players[1] = {"id": 1, "current_day": 1, "current_phase": "visitor",
                             "reputation": 0}
    monkeypatch.setattr(negotiation, "repo", fake_repo)

    # LLM fixture 모드라 자동 응답
    res = await negotiation.step_sell(
        fake_repo.players[1], weapon_id=10, hero_id=1, price_offered=100,
        player_message="첫 제안", neg_id=None,
    )
    neg = fake_repo.get_negotiation(res["negotiation_id"])
    # 깐깐 페르소나 → start 30
    assert neg["patience_start"] == 30
    assert neg["patience_current"] == 20  # 한 라운드 감소


@pytest.mark.asyncio
async def test_step_sell_auto_reject_when_patience_exhausted(fake_repo, monkeypatch):
    fake_repo.heroes.append({
        "id": 1, "player_id": 1, "name": "H", "job": "검사",
        "str": 5, "mag": 5, "personality_tags": ["깐깐", "소심"],
        "affinity": 0, "history": [], "gold": 1000,
    })
    fake_repo.weapons.append({
        "id": 10, "player_id": 1, "owner": "player", "name": "검", "type": "검",
        "rarity": 0, "sharpness": 30, "materials_used": [{"category": "일반"}],
        "attribute": "화",
    })
    fake_repo.materials = [{"id": 1, "category": "일반", "base_price": 50}]
    fake_repo.players[1] = {"id": 1, "current_day": 1, "current_phase": "visitor",
                             "reputation": 5}
    monkeypatch.setattr(negotiation, "repo", fake_repo)

    # 깐깐+소심 → 20. 두 라운드 후 0.
    res = await negotiation.step_sell(
        fake_repo.players[1], 10, 1, 100, "1", None)
    nid = res["negotiation_id"]
    res2 = await negotiation.step_sell(
        fake_repo.players[1], 10, 1, 100, "2", nid)
    # 세 번째 라운드 진입 시 patience_current == 0 → 자동 reject
    res3 = await negotiation.step_sell(
        fake_repo.players[1], 10, 1, 100, "3", nid)
    assert res3["decision"] == "reject"
    assert "참" in res3["message"] or "patience" in res3["message"].lower()
    neg = fake_repo.get_negotiation(nid)
    assert neg["outcome"] == "rejected"
    assert fake_repo.players[1]["reputation"] == 4  # -1
```

- [ ] **Step 2: step_sell 수정**

`backend/app/negotiation.py`의 `step_sell`에서:

(a) 첫 라운드(`neg_id is None`)에서 negotiation insert 직후 `patience_start = patience.hero_start(hero)` 계산해 update:

```python
from . import patience as _pat
if neg_id is None:
    ...
    neg = repo.insert_negotiation(pid, {...})
    neg_id = neg["id"]
    p_start = _pat.hero_start(hero)
    repo.update_negotiation(neg_id, patience_start=p_start, patience_current=p_start)
    prior_rounds = []
else:
    neg = repo.get_negotiation(neg_id)
    prior_rounds = neg["rounds"]
```

(b) 라운드 진입 시점 (`safe_price` 계산 직후) — 이전 라운드 가격 비교해 conceded 여부 판정 후 patience 감소. 단 첫 라운드는 감소 X (시작값 그대로 노출):

```python
neg = repo.get_negotiation(neg_id)  # patience_start/current 포함
p_current = int(neg.get("patience_current") or 0)
if len(prior_rounds) > 0:  # 첫 라운드는 감소 안 함
    last_hero = next((r for r in reversed(prior_rounds) if r["role"] == "hero"), None)
    conceded = False
    if last_hero and last_hero.get("price") is not None and max_hero_counter is not None:
        # hero가 양보 = counter가 직전 hero counter 이상 (이미 단조 비감소이지만, 명시적 ↑면 양보)
        # player 측 양보 = safe_price가 이전 player price보다 낮음
        last_player = next((r for r in reversed(prior_rounds) if r["role"] == "player"), None)
        if last_player and safe_price < int(last_player["price"]):
            conceded = True
    p_current = _pat.next_after_round(p_current, conceded=conceded)
    repo.update_negotiation(neg_id, patience_current=p_current)
```

(c) patience exhausted → 자동 reject (LLM 호출 전에 분기):

```python
if _pat.is_exhausted(p_current):
    # 강제 reject
    repo.update_negotiation(neg_id, outcome="rejected",
                            rounds=prior_rounds + [{"role": "hero", "message": "더는 못 참겠소.", "price": None}])
    player_now = repo.load_player(pid)
    repo.insert_day_event(
        pid, day=player_now["current_day"], phase=player_now["current_phase"],
        kind="patience_exhausted", payload={"by": "hero", "negotiation_id": neg_id, "rep_delta": -1},
    )
    repo.update_player(pid, reputation=max(0, player_now["reputation"] - 1))
    # 호감도 -1
    new_aff = max(-100, int(hero.get("affinity", 0)) - 1)
    repo.update_hero(hero_id, affinity=new_aff)
    return {"negotiation_id": neg_id, "decision": "reject", "counter_price": None,
            "message": "더는 못 참겠소."}
```

- [ ] **Step 3: step_buy도 동일 패턴 적용** — patience.merchant_start로 시작값, 동일 감소/exhausted 로직 (`hero` 자리에 `merchant`/`m_row` 사용).

상인 시작값:
```python
p_start = _pat.merchant_start(pid, player_data["current_day"], m_row["id"])
```

exhausted 시: outcome=rejected, merchant 정리 (`update_merchant_today(m_row["id"], outcome="done")`), 평판 변화 없음(상인 떠남은 손해 없음).

- [ ] **Step 4: Run**

```bash
python -m pytest tests/test_negotiation.py tests/test_patience.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/negotiation.py backend/tests/test_negotiation.py
git commit -m "feat(negotiation): integrate patience — persona start, round decrement, auto-reject"
```

---

### Task 8: step_buy_loot + finalize_buy_loot

**Files:**
- Modify: `backend/app/negotiation.py`
- Create: `backend/tests/test_step_buy_loot.py`

- [ ] **Step 1: 실패 테스트**

```python
# backend/tests/test_step_buy_loot.py
import pytest
from app import negotiation


@pytest.mark.asyncio
async def test_step_buy_loot_starts_with_affinity_weighted_price(fake_repo, monkeypatch):
    fake_repo.heroes.append({
        "id": 1, "player_id": 1, "name": "H", "personality_tags": [],
        "affinity": 0, "loot_pending": [
            {"material_id": 1, "qty": 2},
            {"material_id": 2, "qty": 1},
        ],
        "history": [],
    })
    fake_repo.materials = [
        {"id": 1, "category": "일반", "base_price": 50, "name": "철"},
        {"id": 2, "category": "일반", "base_price": 100, "name": "강철"},
    ]
    fake_repo.players[1] = {"id": 1, "current_day": 1, "gold": 10000,
                             "current_phase": "visitor", "reputation": 0}
    monkeypatch.setattr(negotiation, "repo", fake_repo)

    # base = 50*2 + 100*1 = 200; multiplier = 1.2 - 0/200 = 1.2 → asking 240
    res = await negotiation.step_buy_loot(
        fake_repo.players[1], hero_id=1, price_offered=240,
        player_message="이거 다 살게", neg_id=None,
    )
    assert res["decision"] == "accept"   # 정확히 asking 제시 → 자동 accept


@pytest.mark.asyncio
async def test_step_buy_loot_high_affinity_lowers_price(fake_repo, monkeypatch):
    fake_repo.heroes.append({
        "id": 1, "player_id": 1, "name": "H", "personality_tags": [],
        "affinity": 100, "loot_pending": [{"material_id": 1, "qty": 2}],
        "history": [],
    })
    fake_repo.materials = [{"id": 1, "category": "일반", "base_price": 50, "name": "철"}]
    fake_repo.players[1] = {"id": 1, "current_day": 1, "gold": 10000,
                             "current_phase": "visitor", "reputation": 0}
    monkeypatch.setattr(negotiation, "repo", fake_repo)

    # multiplier = 1.2 - 100/200 = 0.7 → asking 70 (base 100)
    res = await negotiation.step_buy_loot(
        fake_repo.players[1], hero_id=1, price_offered=70,
        player_message="고맙다", neg_id=None,
    )
    assert res["decision"] == "accept"


def test_finalize_buy_loot_transfers_inventory_and_bumps_affinity(fake_repo, monkeypatch):
    fake_repo.heroes.append({
        "id": 1, "player_id": 1, "name": "H",
        "affinity": 10, "loot_pending": [{"material_id": 1, "qty": 2}],
        "history": [],
    })
    fake_repo.materials = [{"id": 1, "category": "일반", "base_price": 50, "name": "철"}]
    fake_repo.players[1] = {"id": 1, "current_day": 1, "gold": 1000,
                             "current_phase": "visitor", "reputation": 0}
    fake_repo.negotiations.append({
        "id": 1, "player_id": 1, "kind": "buy_loot", "counterparty_id": 1,
        "outcome": "accepted", "agreed_price": 100,
        "materials": {"items": [{"material_id": 1, "qty": 2}]},
        "rounds": [],
    })
    fake_repo._neg_seq = 1
    monkeypatch.setattr(negotiation, "repo", fake_repo)

    negotiation.finalize_buy_loot(fake_repo.players[1], 1)
    assert fake_repo.players[1]["gold"] == 900
    inv = fake_repo.inventory[1]
    assert any(r["material_id"] == 1 and r["qty"] == 2 for r in inv)
    h = fake_repo.get_hero(1)
    assert h["affinity"] == 15  # +5
    assert h["loot_pending"] == []
```

- [ ] **Step 2: 구현 — negotiation.py에 추가**

```python
async def step_buy_loot(player: dict, hero_id: int, price_offered: int,
                         player_message: str, neg_id: int | None) -> dict[str, Any]:
    """전리품 매수 협상. step_buy 패턴 + 호감도 가중 시작가."""
    pid = player["id"]
    hero = repo.get_hero(hero_id)
    if not hero:
        raise ValueError("hero not found")
    loot = hero.get("loot_pending") or []

    if neg_id is None:
        if not loot:
            raise ValueError("hero has no loot to sell")
        # 시작가 = sum(base_price * qty) * (1.2 - affinity/200)
        total = 0
        for it in loot:
            m = repo.get_material(it["material_id"]) if hasattr(repo, "get_material") else None
            # FakeRepo는 materials 리스트 보유; 운영 repo도 get_material 헬퍼 사용
            if m is None:
                # fallback: list_materials_by_category 폴링 (느리지만 안전)
                for cat in ("일반", "이상한", "특수", "전설"):
                    pool = repo.list_materials_by_category(cat)
                    m = next((x for x in pool if x["id"] == it["material_id"]), None)
                    if m: break
            total += int(m["base_price"] if m else 0) * int(it["qty"])
        affinity = int(hero.get("affinity", 0))
        multiplier = max(0.5, 1.2 - affinity / 200.0)
        asking = max(1, int(total * multiplier))

        player_data = repo.load_player(pid)
        neg = repo.insert_negotiation(pid, {
            "day": player_data["current_day"], "phase": player_data["current_phase"],
            "kind": "buy_loot", "counterparty_id": hero_id, "weapon_id": None,
            "materials": {"items": loot, "asking": asking},
            "rounds": [], "outcome": "open",
        })
        neg_id = neg["id"]
        from . import patience as _pat
        p_start = _pat.hero_start(hero)
        repo.update_negotiation(neg_id, patience_start=p_start, patience_current=p_start)
        prior_rounds = []
        base = asking
    else:
        neg = repo.get_negotiation(neg_id)
        prior_rounds = neg["rounds"]
        base = int((neg["materials"] or {}).get("asking", 1))

    # ... step_buy와 동일한 양보 로직 (5% 양보, 70% floor, auto-accept)
    # 인내심 감소 + exhausted 처리 (Task 7과 동일)
    # (이하 step_buy 본문 복사 후 다듬기)

    # 간소화: 자동 accept만 핵심 구현
    player_now = repo.load_player(pid)
    safe_price = max(1, min(int(price_offered), int(player_now.get("gold", 0))))
    merch_prior = [int(r["price"]) for r in prior_rounds
                   if r["role"] == "hero" and r.get("price") is not None]
    min_counter = min(merch_prior) if merch_prior else None

    from . import patience as _pat
    p_current = int(neg.get("patience_current") or _pat.hero_start(hero))
    if len(prior_rounds) > 0:
        p_current = _pat.next_after_round(p_current, conceded=False)
        repo.update_negotiation(neg_id, patience_current=p_current)
    if _pat.is_exhausted(p_current):
        repo.update_negotiation(neg_id, outcome="rejected")
        return {"negotiation_id": neg_id, "decision": "reject", "counter_price": None,
                "message": "더는 못 참겠소. 전리품은 다른 데 팔겠소."}

    threshold = min_counter if min_counter is not None else base
    if safe_price >= threshold:
        repo.update_negotiation(neg_id, outcome="accepted", agreed_price=safe_price,
                                rounds=prior_rounds + [
                                    {"role": "player", "message": player_message, "price": safe_price},
                                    {"role": "hero", "message": f"좋소, {safe_price}골드에 드리지요.", "price": None},
                                ])
        return {"negotiation_id": neg_id, "decision": "accept", "counter_price": None,
                "message": f"좋소, {safe_price}골드에 드리지요."}

    # 카운터: 시작가의 95% 양보 (조금씩만), floor=시작가*0.7
    previous = min_counter if min_counter is not None else base
    counter = max(int(base * 0.7), previous - int(previous * 0.05))
    if counter <= safe_price:
        repo.update_negotiation(neg_id, outcome="accepted", agreed_price=safe_price,
                                rounds=prior_rounds + [
                                    {"role": "player", "message": player_message, "price": safe_price},
                                    {"role": "hero", "message": f"좋소, {safe_price}골드.", "price": None},
                                ])
        return {"negotiation_id": neg_id, "decision": "accept", "counter_price": None,
                "message": f"좋소, {safe_price}골드."}
    repo.update_negotiation(neg_id, rounds=prior_rounds + [
        {"role": "player", "message": player_message, "price": safe_price},
        {"role": "hero", "message": f"그건 너무 싸오. {counter}골드는 받아야 하오.", "price": counter},
    ])
    return {"negotiation_id": neg_id, "decision": "counter", "counter_price": counter,
            "message": f"그건 너무 싸오. {counter}골드는 받아야 하오."}


def finalize_buy_loot(player: dict, neg_id: int) -> bool:
    pid = player["id"]
    neg = repo.get_negotiation(neg_id)
    if neg.get("finalized"):
        return False
    if neg["outcome"] != "accepted":
        raise ValueError("negotiation not accepted")
    repo.update_negotiation(neg_id, finalized=True)
    player_now = repo.load_player(pid)
    price = int(neg["agreed_price"])
    items = (neg.get("materials") or {}).get("items") or []
    if price > int(player_now.get("gold", 0)):
        raise ValueError("insufficient gold")
    repo.update_player(pid, gold=player_now["gold"] - price)
    for it in items:
        repo.add_inventory(pid, int(it["material_id"]), int(it["qty"]))
    hero_id = int(neg["counterparty_id"])
    hero = repo.get_hero(hero_id)
    from . import affinity as affinity_mod
    new_aff = affinity_mod.clamp_affinity(int(hero.get("affinity", 0)) + 5)
    repo.update_hero(hero_id, affinity=new_aff)
    repo.clear_hero_loot(hero_id)
    repo.insert_day_event(
        pid, day=player_now["current_day"], phase=player_now["current_phase"],
        kind="loot_sale",
        payload={"negotiation_id": neg_id, "hero_id": hero_id, "price": price,
                 "items": items, "affinity_delta": 5},
    )
    return True
```

또한 `repo.py` 에 `get_material(material_id)` 헬퍼 추가 (작은 변경):

```python
def get_material(material_id: int) -> dict[str, Any] | None:
    rows = _client().table("materials").select("*").eq("id", material_id).limit(1).execute().data
    return rows[0] if rows else None
```

FakeRepo에도:
```python
def get_material(self, material_id: int):
    return next((m for m in self.materials if m["id"] == material_id), None)
```

- [ ] **Step 3: Run**

```bash
python -m pytest tests/test_step_buy_loot.py -v
```
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/negotiation.py backend/app/repo.py backend/tests/fake_repo.py backend/tests/test_step_buy_loot.py
git commit -m "feat(negotiation): step_buy_loot + finalize_buy_loot with affinity-weighted pricing"
```

---

### Task 9: /api/loot 엔드포인트

**Files:**
- Create: `backend/app/api/loot.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 구현**

```python
# backend/app/api/loot.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from .. import repo, negotiation, state_machine
from ..api.visitor import advance as advance_visitor_phase
from ..auth import current_player

router = APIRouter(prefix="/loot", tags=["loot"])


class NegotiateReq(BaseModel):
    price_offered: int
    player_message: str = ""
    negotiation_id: int | None = None


class FinalizeReq(BaseModel):
    negotiation_id: int


def _current_hero_id(player: dict) -> int:
    try:
        state_machine.assert_phase(player["current_phase"], "visitor")
    except state_machine.PhaseError:
        raise HTTPException(400, detail={"error": "wrong_phase"})
    sched = player.get("day_schedule") or []
    idx = player.get("current_visitor_index", 0)
    if idx >= len(sched):
        raise HTTPException(409, "no current visitor")
    slot = sched[idx]
    if slot["kind"] != "returning_hero":
        raise HTTPException(409, "loot trade only for returning_hero")
    return slot["hero_id"]


@router.post("/negotiate")
async def post_negotiate(req: NegotiateReq, player: dict = Depends(current_player)):
    hero_id = _current_hero_id(player)
    try:
        return await negotiation.step_buy_loot(
            player, hero_id, req.price_offered, req.player_message, req.negotiation_id,
        )
    except ValueError as e:
        raise HTTPException(400, detail={"error": "invalid", "message": str(e)})


@router.post("/player_accept")
async def post_player_accept(req: FinalizeReq, player: dict = Depends(current_player)):
    neg = repo.get_negotiation(req.negotiation_id)
    if not neg or neg["outcome"] not in ("open", "accepted"):
        raise HTTPException(400, detail={"error": "cannot_accept"})
    if neg["outcome"] == "open":
        # 가장 최근 hero counter를 합의가로
        hero_counters = [int(r["price"]) for r in neg["rounds"]
                         if r["role"] == "hero" and r.get("price") is not None]
        if not hero_counters:
            raise HTTPException(400, detail={"error": "no counter"})
        agreed = int(hero_counters[-1])
        repo.update_negotiation(req.negotiation_id, outcome="accepted", agreed_price=agreed)
    try:
        negotiation.finalize_buy_loot(player, req.negotiation_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_finalize", "message": str(e)})
    return {"ok": True, "current_phase": player["current_phase"]}


@router.post("/finalize")
def post_finalize(req: FinalizeReq, player: dict = Depends(current_player)):
    try:
        negotiation.finalize_buy_loot(player, req.negotiation_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_finalize", "message": str(e)})
    return {"ok": True}


@router.post("/player_reject")
def post_player_reject(req: FinalizeReq, player: dict = Depends(current_player)):
    repo.update_negotiation(req.negotiation_id, outcome="rejected")
    return {"ok": True}
```

- [ ] **Step 2: main.py 라우터 등록**

```python
from .api import ..., loot as loot_api
app.include_router(loot_api.router)
```

- [ ] **Step 3: 임포트 검증 + Commit**

```bash
python -c "from app.main import app; print('OK')"
git add backend/app/api/loot.py backend/app/main.py
git commit -m "feat(api): /loot/{negotiate,player_accept,player_reject,finalize}"
```

---

### Task 10: chitchat 모듈 + 엔드포인트 + LLM

**Files:**
- Create: `backend/app/chitchat.py`
- Create: `backend/app/api/chitchat.py`
- Create: `backend/app/llm/prompts/chitchat.j2`
- Create: `backend/tests/fixtures/llm/chitchat.json`
- Create: `backend/tests/test_chitchat.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 프롬프트 + fixture**

`backend/app/llm/prompts/chitchat.j2`:
```jinja
당신은 {{ hero.name }}({{ hero.job }}). 페르소나: {{ hero.personality_tags | join(", ") }}.
대장장이와 가게에서 잠깐 잡담을 합니다.

지난 대화 기록 (최근 3개):
{% for l in recent_lore %}- {{ l.text }}
{% endfor %}

플레이어가 던진 말: {{ player_message or "(별 말 없음)" }}

당신의 캐릭터에 맞는 톤으로 자기 근황·과거·싸운 적·마을 소문 중 하나를 한 문단(3~5문장)으로 풀어놓으세요.
JSON으로만 응답: {"lore_text": "..."}
```

`backend/tests/fixtures/llm/chitchat.json`:
```json
{"lore_text": "지난주에 마을 외곽에서 임프 떼를 만났는데, 한 놈이 유난히 작아서 도망치는 걸 따라가 봤지. 그 굴에 묘한 기운이 있더이다. 나중에 한 번 더 살펴볼 생각이오."}
```

- [ ] **Step 2: chitchat.py**

```python
# backend/app/chitchat.py
"""chitchat 서비스 — LLM 한 문단 → heroes.lore 누적."""
from __future__ import annotations
from typing import Any
from . import repo
from .llm.client import complete_json


async def converse(player: dict[str, Any], hero: dict[str, Any],
                    player_message: str = "") -> dict[str, Any]:
    if int(hero.get("affinity", 0)) < 0:
        raise ValueError("affinity_too_low")
    recent_lore = (hero.get("lore") or [])[-3:]
    llm = await complete_json("chitchat", "chitchat",
                              hero=hero,
                              recent_lore=recent_lore,
                              player_message=player_message,
                              recent_history=(hero.get("history") or [])[-3:])
    text = llm.get("lore_text", "...")
    entry = {"day": player["current_day"], "text": text}
    repo.append_hero_lore(hero["id"], entry, cap=20)
    return {"lore_text": text, "entry": entry}
```

- [ ] **Step 3: 엔드포인트**

```python
# backend/app/api/chitchat.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from .. import repo, state_machine, chitchat
from ..auth import current_player

router = APIRouter(tags=["chitchat"])


class ChitchatReq(BaseModel):
    player_message: str = ""


@router.post("/visitor/current/chitchat")
async def post_chitchat(req: ChitchatReq, player: dict = Depends(current_player)):
    try:
        state_machine.assert_phase(player["current_phase"], "visitor")
    except state_machine.PhaseError:
        raise HTTPException(400, detail={"error": "wrong_phase"})
    sched = player.get("day_schedule") or []
    idx = player.get("current_visitor_index", 0)
    if idx >= len(sched):
        raise HTTPException(409, "no current visitor")
    slot = sched[idx]
    if slot["kind"] not in ("new_hero", "returning_hero"):
        raise HTTPException(409, "chitchat only with heroes")
    hero = repo.get_hero(slot["hero_id"])
    if not hero:
        raise HTTPException(404, "hero not found")
    try:
        return await chitchat.converse(player, hero, req.player_message)
    except ValueError as e:
        raise HTTPException(400, detail={"error": str(e)})
```

- [ ] **Step 4: 테스트**

```python
# backend/tests/test_chitchat.py
from unittest.mock import patch
import pytest
from app import chitchat


@pytest.mark.asyncio
async def test_converse_appends_lore(fake_repo, monkeypatch):
    hero = {"id": 1, "name": "H", "job": "검사", "personality_tags": [],
            "affinity": 0, "history": [], "lore": []}
    fake_repo.heroes.append(hero)
    monkeypatch.setattr(chitchat, "repo", fake_repo)
    player = {"id": 1, "current_day": 5}
    result = await chitchat.converse(player, hero, "안녕")
    assert "lore_text" in result
    h = fake_repo.get_hero(1)
    assert len(h["lore"]) == 1
    assert h["lore"][0]["day"] == 5


@pytest.mark.asyncio
async def test_converse_blocked_by_negative_affinity(fake_repo, monkeypatch):
    hero = {"id": 1, "name": "H", "job": "검사", "personality_tags": [],
            "affinity": -10, "history": [], "lore": []}
    monkeypatch.setattr(chitchat, "repo", fake_repo)
    with pytest.raises(ValueError):
        await chitchat.converse({"id": 1, "current_day": 1}, hero, "")


@pytest.mark.asyncio
async def test_converse_caps_lore_at_20(fake_repo, monkeypatch):
    hero = {"id": 1, "name": "H", "job": "검사", "personality_tags": [],
            "affinity": 0, "history": [],
            "lore": [{"day": d, "text": f"old {d}"} for d in range(20)]}
    fake_repo.heroes.append(hero)
    monkeypatch.setattr(chitchat, "repo", fake_repo)
    await chitchat.converse({"id": 1, "current_day": 99}, hero, "")
    h = fake_repo.get_hero(1)
    assert len(h["lore"]) == 20
    assert h["lore"][-1]["day"] == 99
    assert h["lore"][0]["day"] == 1  # day 0이 drop
```

- [ ] **Step 5: main.py 라우터 등록 + Run + Commit**

```python
from .api import ..., chitchat as chitchat_api
app.include_router(chitchat_api.router)
```

```bash
python -m pytest tests/test_chitchat.py -v
```
Expected: PASS.

```bash
git add backend/app/chitchat.py backend/app/api/chitchat.py backend/app/llm/prompts/chitchat.j2 backend/tests/fixtures/llm/chitchat.json backend/tests/test_chitchat.py backend/app/main.py
git commit -m "feat(chitchat): /visitor/current/chitchat appends LLM paragraph to hero.lore"
```

---

### Task 11: /state hydrate 확장

**Files:**
- Modify: `backend/app/api/state.py`

- [ ] **Step 1: hero 슬롯 hydrate에 lore/loot_pending/active_negotiation 추가**

`_hydrate_visitor` 함수의 new_hero/returning_hero 분기에서, hero 객체에 다음 필드 포함하도록:

```python
# 기존:
hydrated["hero"] = {**h, "preferences": hero_registry.preferences_for(h), ...}

# 추가:
hydrated["hero"]["lore"] = h.get("lore") or []
hydrated["hero"]["loot_pending"] = h.get("loot_pending") or []
```

(이미 `**h`로 펼치므로 컬럼이 있으면 자동 포함됨. 명시 추가로 보장.)

- [ ] **Step 2: 임포트 확인**

```bash
python -c "from app.api import state; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/state.py
git commit -m "feat(state): expose hero.lore + hero.loot_pending to client"
```

---

### Task 12: 프론트 타입 + API 래퍼

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/api.ts`

- [ ] **Step 1: 타입 추가**

```typescript
// frontend/src/types.ts 끝에:
export interface LoreEntry { day: number; text: string; }
export interface LootItem { material_id: number; qty: number; asking_price?: number; name?: string; }

// Hero 인터페이스에 (기존 정의에 필드 추가):
//   lore?: LoreEntry[];
//   loot_pending?: LootItem[];

// Negotiation 응답 등에 patience 추가하고 싶으면:
export interface NegotiationPatience { current: number; start: number; level: "high" | "low" | "exhausted"; }
```

`Hero` 인터페이스 본문 찾아서 lore/loot_pending 옵셔널 추가.

- [ ] **Step 2: API 래퍼 추가 — `frontend/src/api.ts`**

```typescript
// chitchat
chitchat: (message: string = "") =>
  request<{ lore_text: string; entry: LoreEntry }>("POST", "/visitor/current/chitchat", { player_message: message }),

// loot
lootNegotiate: (price_offered: number, player_message: string, negotiation_id: number | null = null) =>
  request<NegotiateResponse>("POST", "/loot/negotiate", { price_offered, player_message, negotiation_id }),
lootPlayerAccept: (negotiation_id: number) =>
  request<{ ok: true; current_phase: string }>("POST", "/loot/player_accept", { negotiation_id }),
lootPlayerReject: (negotiation_id: number) =>
  request<{ ok: true }>("POST", "/loot/player_reject", { negotiation_id }),
lootFinalize: (negotiation_id: number) =>
  request<{ ok: true }>("POST", "/loot/finalize", { negotiation_id }),
```

`LoreEntry` import도 types에서 추가.

- [ ] **Step 3: 타입체크 + Commit**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

```bash
git add frontend/src/types.ts frontend/src/api.ts
git commit -m "feat(frontend): types + api wrappers for chitchat/loot/lore"
```

---

### Task 13: PatienceGauge + 기존 협상 컴포넌트 통합

**Files:**
- Create: `frontend/src/components/PatienceGauge.tsx`
- Modify: `frontend/src/components/NegotiationChat.tsx`
- Modify: `frontend/src/components/MerchantPanel.tsx`
- Modify: `frontend/src/components/EnhanceNegotiation.tsx`

- [ ] **Step 1: PatienceGauge 컴포넌트**

```tsx
// frontend/src/components/PatienceGauge.tsx
export function PatienceGauge({ current, start, label = "인내심" }: { current: number; start: number; label?: string }) {
  const pct = Math.max(0, Math.min(100, (current / Math.max(start, 1)) * 100));
  const color = current <= 0 ? "#888" : current <= 30 ? "#d33" : pct >= 60 ? "#3a3" : "#da3";
  return (
    <div style={{ margin: "4px 0", fontSize: 13 }}>
      <span>{label}: {current}/{start}</span>
      <div style={{ background: "#eee", height: 6, borderRadius: 3, overflow: "hidden", marginTop: 2 }}>
        <div style={{ width: `${pct}%`, background: color, height: "100%" }} />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: NegotiationChat에 게이지**

기존 NegotiationChat 상단(h2 아래)에:

```tsx
import { PatienceGauge } from "./PatienceGauge";
// last 또는 negotiation 응답에서 patience_start/current 받음 (백엔드가 노출하면)
// 응답에 없으면 일단 hero personality 기반 추정값으로 표시 — 단순화 위해 백엔드 응답에서 받기
// 응답 객체에 patience_current, patience_start 추가하도록 step_sell return 보강 필요
```

⚠️ **백엔드 보강 필요**: `step_sell`/`step_buy`/`step_buy_loot`/`step_enhance` 반환 dict에 `patience_current`, `patience_start` 포함시켜야 함. Task 7-8에서 누락된 부분이라 여기서 보강:

`negotiation.py` 각 step_* 마지막 return 직전에:
```python
neg_now = repo.get_negotiation(neg_id)
patience_pack = {"patience_current": neg_now.get("patience_current"),
                 "patience_start": neg_now.get("patience_start")}
return {..., **patience_pack}
```

그리고 NegotiationChat에:
```tsx
{last && last.patience_current != null && last.patience_start != null && (
  <PatienceGauge current={last.patience_current} start={last.patience_start} label={`${hero.name}의 인내심`} />
)}
```

- [ ] **Step 3: MerchantPanel + EnhanceNegotiation에도 동일 패턴**

- [ ] **Step 4: 타입체크 + 백엔드 회귀**

```bash
cd frontend && npx tsc --noEmit
cd ../backend && source .venv/bin/activate && python -m pytest -q
```
Expected: 모두 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/negotiation.py frontend/src/components/PatienceGauge.tsx frontend/src/components/NegotiationChat.tsx frontend/src/components/MerchantPanel.tsx frontend/src/components/EnhanceNegotiation.tsx
git commit -m "feat(frontend): PatienceGauge in negotiation panels; backend returns patience fields"
```

---

### Task 14: HeroVisitorPanel — 메뉴식

**Files:**
- Create: `frontend/src/components/HeroVisitorPanel.tsx`
- Modify: `frontend/src/components/VisitorRouter.tsx`
- Delete: `frontend/src/components/ReturningHeroPanel.tsx`

- [ ] **Step 1: HeroVisitorPanel 작성**

```tsx
// frontend/src/components/HeroVisitorPanel.tsx
import { useState } from "react";
import type { CurrentVisitor, StateResponse } from "../types";
import { api } from "../api";
import { NegotiationChat } from "./NegotiationChat";
import { EnhanceNegotiation } from "./EnhanceNegotiation";
import { LootNegotiation } from "./LootNegotiation";
import { ChitchatPanel } from "./ChitchatPanel";

type Mode = "menu" | "sell" | "enhance" | "loot" | "chitchat";

export function HeroVisitorPanel({
  state, visitor, refresh,
}: { state: StateResponse; visitor: CurrentVisitor; refresh: () => void }) {
  const [mode, setMode] = useState<Mode>("menu");
  const hero = visitor.hero;
  if (!hero) return <p>용사 정보를 불러오는 중...</p>;

  const isReturning = visitor.kind === "returning_hero";
  const hasWeapons = state.weapons.length > 0;
  const hasHeld = hero.mode === "enhance" && !!hero.held_weapon;
  const hasLoot = (hero.loot_pending && hero.loot_pending.length > 0) ?? false;
  const canChitchat = (hero.affinity ?? 0) >= 0;

  const returnToMenu = async () => { await refresh(); setMode("menu"); };
  const sendAway = async () => {
    if (isReturning) await api.visitorReturn();
    else await api.visitorSkip();
    refresh();
  };

  if (mode === "sell" && hasWeapons) {
    return <NegotiationChat hero={hero} weapons={state.weapons} onDone={returnToMenu} />;
  }
  if (mode === "enhance" && hasHeld) {
    return <EnhanceNegotiation hero={hero} weapon={hero.held_weapon!} inventory={state.inventory} onDone={returnToMenu} />;
  }
  if (mode === "loot" && hasLoot) {
    return <LootNegotiation hero={hero} onDone={returnToMenu} />;
  }
  if (mode === "chitchat") {
    return <ChitchatPanel hero={hero} onDone={returnToMenu} />;
  }

  // menu
  return (
    <div>
      <h2>
        {hero.name}{hero.nickname ? ` "${hero.nickname}"` : ""} ({hero.job})
        {isReturning && <small style={{ marginLeft: 8, color: "#a06" }}>· 재방문 🔁</small>}
      </h2>
      {isReturning && visitor.recap && (
        <div style={{ background: "#f8f4ee", padding: 12, borderRadius: 6, margin: "8px 0" }}>
          <strong>지난 출정 회고</strong>
          <p style={{ whiteSpace: "pre-wrap", marginTop: 4 }}>{visitor.recap}</p>
        </div>
      )}
      <p>호감도 {hero.affinity ?? 0} · 보유 금화 {hero.gold ?? 0}</p>
      <div style={{ display: "grid", gap: 8, marginTop: 12 }}>
        <button className="btn" disabled={!hasWeapons} onClick={() => setMode("sell")}>
          무기 판매 {!hasWeapons && "(인벤토리 비어있음)"}
        </button>
        <button className="btn" disabled={!hasHeld} onClick={() => setMode("enhance")}>
          무기 강화 {!hasHeld && "(들고 있는 무기 없음)"}
        </button>
        <button className="btn" disabled={!hasLoot} onClick={() => setMode("loot")}>
          전리품 매수 {!hasLoot && "(전리품 없음)"}
        </button>
        <button className="btn" disabled={!canChitchat} onClick={() => setMode("chitchat")}>
          잡담 {!canChitchat && "(호감도 부족)"}
        </button>
        <button className="btn" onClick={sendAway}>보내기</button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: VisitorRouter 수정 — hero kind 모두 HeroVisitorPanel**

```tsx
// VisitorRouter.tsx
import { HeroVisitorPanel } from "./HeroVisitorPanel";
// returning_hero 분기 제거, new_hero/returning_hero 둘 다 HeroVisitorPanel로:
if (v.kind === "new_hero" || v.kind === "returning_hero") {
  return <HeroVisitorPanel key={slotKey} state={state} visitor={v} refresh={refresh} />;
}
// merchant만 별도
```

- [ ] **Step 3: ReturningHeroPanel 삭제**

```bash
git rm frontend/src/components/ReturningHeroPanel.tsx
```

- [ ] **Step 4: 타입체크**

```bash
cd frontend && npx tsc --noEmit
```
(LootNegotiation, ChitchatPanel은 다음 Task에서 만듦 → 임시 stub 필요)

- [ ] **Step 5: stub 만들기** (15/16 Task 전까지 컴파일 통과용)

```tsx
// LootNegotiation.tsx 스텁
import type { Hero } from "../types";
export function LootNegotiation({ hero, onDone }: { hero: Hero; onDone: () => void }) {
  return <div><p>전리품 협상 (구현 중)</p><button onClick={onDone}>돌아가기</button></div>;
}
// ChitchatPanel.tsx 스텁 동일 패턴
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(frontend): HeroVisitorPanel menu replaces ReturningHeroPanel; sub-panels routed"
```

---

### Task 15: LootNegotiation 컴포넌트

**Files:**
- Modify (스텁→실제): `frontend/src/components/LootNegotiation.tsx`

- [ ] **Step 1: 구현**

```tsx
import { useState } from "react";
import type { Hero, NegotiateResponse } from "../types";
import { api } from "../api";
import { PatienceGauge } from "./PatienceGauge";

export function LootNegotiation({ hero, onDone }: { hero: Hero; onDone: () => void }) {
  const loot = hero.loot_pending ?? [];
  const [price, setPrice] = useState(0);
  const [text, setText] = useState("");
  const [last, setLast] = useState<NegotiateResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const send = async () => {
    setBusy(true); setErr(null);
    try {
      const res = await api.lootNegotiate(price, text, last?.negotiation_id ?? null);
      setLast(res);
      if (res.counter_price) setPrice(res.counter_price);
    } catch (e) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };
  const accept = async () => {
    if (!last) return;
    setBusy(true);
    try { await api.lootPlayerAccept(last.negotiation_id); onDone(); }
    catch (e) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };
  const reject = async () => {
    if (last) await api.lootPlayerReject(last.negotiation_id);
    onDone();
  };

  return (
    <div>
      <h2>전리품 매수 — {hero.name}</h2>
      <ul>
        {loot.map((it, i) => (
          <li key={i}>재료 #{it.material_id} × {it.qty}</li>
        ))}
      </ul>
      {last && (last as any).patience_current != null && (
        <PatienceGauge current={(last as any).patience_current} start={(last as any).patience_start} label={`${hero.name}의 인내심`} />
      )}
      {last && (
        <div style={{ margin: "8px 0", padding: 8, background: "#f5f5f5" }}>
          <strong>{hero.name}:</strong> {last.message}
          {last.counter_price != null && <em> ({last.counter_price} 골드)</em>}
        </div>
      )}
      <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
        <label>제시 가격:&nbsp;
          <input type="number" value={price} onChange={(e) => setPrice(Math.max(0, Number(e.target.value)))} />
        </label>
        <textarea rows={2} style={{ width: "100%" }} value={text} onChange={(e) => setText(e.target.value)} placeholder="용사에게 한마디 (선택)" />
      </div>
      <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
        <button className="btn" disabled={busy} onClick={send}>{last ? "재제안" : "제안"}</button>
        {last?.counter_price != null && (
          <button className="btn" disabled={busy} onClick={accept}>{last.counter_price} 골드에 수락</button>
        )}
        <button className="btn" disabled={busy} onClick={reject}>거절하고 돌아가기</button>
      </div>
      {err && <p style={{ color: "crimson" }}>{err}</p>}
    </div>
  );
}
```

- [ ] **Step 2: 타입체크 + Commit**

```bash
cd frontend && npx tsc --noEmit
git add frontend/src/components/LootNegotiation.tsx
git commit -m "feat(frontend): LootNegotiation panel with patience gauge"
```

---

### Task 16: ChitchatPanel 컴포넌트

**Files:**
- Modify (스텁→실제): `frontend/src/components/ChitchatPanel.tsx`

- [ ] **Step 1: 구현**

```tsx
import { useState } from "react";
import type { Hero } from "../types";
import { api } from "../api";

export function ChitchatPanel({ hero, onDone }: { hero: Hero; onDone: () => void }) {
  const [msg, setMsg] = useState("");
  const [resp, setResp] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const talk = async () => {
    setBusy(true); setErr(null);
    try {
      const r = await api.chitchat(msg);
      setResp(r.lore_text);
      setMsg("");
    } catch (e) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  const lore = hero.lore ?? [];

  return (
    <div>
      <h2>잡담 — {hero.name}</h2>
      <textarea rows={2} style={{ width: "100%" }} value={msg} onChange={(e) => setMsg(e.target.value)}
                placeholder="할 말 (비워두면 그냥 듣기)" />
      <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
        <button className="btn" disabled={busy} onClick={talk}>이야기 듣기</button>
        <button className="btn" onClick={onDone}>돌아가기</button>
      </div>
      {err && <p style={{ color: "crimson" }}>{err}</p>}
      {resp && (
        <div style={{ marginTop: 12, padding: 12, background: "#f0f4f8", borderRadius: 6 }}>
          <p style={{ whiteSpace: "pre-wrap" }}>{resp}</p>
        </div>
      )}
      {lore.length > 0 && (
        <details style={{ marginTop: 12 }}>
          <summary>지난 잡담 기록 ({lore.length})</summary>
          <ul style={{ marginTop: 4 }}>
            {lore.slice().reverse().map((l, i) => (
              <li key={i}>[Day {l.day}] {l.text}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
```

- [ ] **Step 2: 타입체크 + Commit**

```bash
cd frontend && npx tsc --noEmit
git add frontend/src/components/ChitchatPanel.tsx
git commit -m "feat(frontend): ChitchatPanel with response display + lore history"
```

---

### Task 17: 회귀 + 수동 검증

- [ ] **Step 1: 전체 백엔드 테스트**

```bash
cd backend && source .venv/bin/activate && python -m pytest -q
```
Expected: 모두 PASS (179 + 신규 약 25 = ~204).

- [ ] **Step 2: 프론트 타입체크**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: 마이그레이션 011 적용 안내**

사용자에게 Supabase MCP `apply_migration` 또는 Studio SQL Editor로 `backend/migrations/011_loot_chitchat_patience.sql` 적용 요청.

- [ ] **Step 4: 수동 브라우저 검증 시나리오**

uvicorn + vite dev 띄운 뒤 새 닉네임으로:
1. forge → 무기 제작
2. 신규 용사 슬롯 → 메뉴 표시 확인 → 잡담 → lore 추가 확인
3. 무기 판매 협상 → 인내심 게이지 표시 → 라운드 진행하면 줄어듦 → 깐깐한 페르소나로 0 도달 → 자동 reject
4. 며칠 진행 → 재방문 용사 슬롯 → 회고 + 메뉴 → 전리품 매수 협상 → accept → 인벤토리 추가, 호감도 +5
5. 호감도 음수 (인위적으로 -10) → 잡담 버튼 비활성 확인

- [ ] **Step 5: 마무리 commit (있다면)**

```bash
git status
# 깔끔하면 끝.
```

---

## 자가 점검

**Spec coverage:**
- 마이그레이션 011 (heroes.lore, loot_pending, negotiations.patience_*) → Task 1
- FakeRepo / repo 확장 → Task 2, 3, 8(get_material)
- 인내심 모듈 + 통합 → Task 4, 7
- loot_table → Task 5
- dispatch loot 통합 → Task 6
- step_buy_loot + finalize_buy_loot → Task 8
- /loot/* 엔드포인트 → Task 9
- chitchat (모듈 + 엔드포인트 + LLM 프롬프트 + fixture) → Task 10
- /state hero hydrate에 lore/loot_pending 포함 → Task 11
- 프론트 타입/API → Task 12
- PatienceGauge + 기존 협상 통합 → Task 13
- HeroVisitorPanel 메뉴식 → Task 14
- LootNegotiation → Task 15
- ChitchatPanel → Task 16
- 회귀 + 수동 검증 → Task 17

**Out of scope (스펙 합의대로):**
- 무기 수리/반환
- 도감 UI
- 미션 NPC (3차)
- 상인 재료 진행도 (4차)
- 무기 칭호 (4차)

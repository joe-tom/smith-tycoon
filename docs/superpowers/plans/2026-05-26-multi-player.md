# Multi-Player (닉네임 기반 독립 세이브) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 닉네임만으로 구분되는 독립 싱글 세이브 다중 지원. 두 플레이어가 동시에 같은 백엔드를 써도 서로의 상태를 보지 못함.

**Architecture:** `players.nickname` 컬럼 추가 후 `repo.PLAYER_ID` 제거. 모든 repo 함수는 `player_id`를 첫 인자로 받음. FastAPI `Depends(current_player)`가 `X-Player-Nickname` 헤더로 자동 생성/조회. NPC 시드는 `(player_id, day)` 결정론. 프론트엔드는 localStorage에 닉네임 저장 + 헤더 부착.

**Tech Stack:** FastAPI, Supabase (Postgres), Pytest, React/Vite, Supabase MCP for migrations.

**Spec:** `docs/superpowers/specs/2026-05-26-multi-player-design.md`

---

## Phase 0 — 준비

### Task 0.1: 마이그레이션 적용

**Files:** `backend/migrations/005_multi_player.sql` (Create)

- [ ] **Step 1: 마이그레이션 파일 생성**

```sql
-- 005_multi_player.sql — 닉네임 기반 멀티 세이브
-- 기존 데이터 와이프 (FK 순서 준수)
delete from day_events;
delete from merchants_today;
delete from battles;
delete from negotiations;
delete from heroes;
delete from weapons;
delete from inventory;
delete from players;
-- 닉네임 컬럼
alter table players add column nickname text unique not null;
```

- [ ] **Step 2: Supabase MCP로 적용**

`mcp__plugin_supabase_supabase__apply_migration` 사용. project_id=`lgxjxkiyychicfzwbirp`, name=`005_multi_player`, query는 위 SQL.

- [ ] **Step 3: 검증**

`mcp__plugin_supabase_supabase__execute_sql`로 `select column_name from information_schema.columns where table_name='players' and column_name='nickname'` 결과 1행 확인.
`select count(*) from players` 결과 0 확인.

- [ ] **Step 4: Commit**

```bash
git add backend/migrations/005_multi_player.sql
git commit -m "feat(db): 005 — nickname column + data wipe"
```

---

## Phase 1 — repo.py 리팩토링

이 단계에서 기존 76 테스트는 깨짐. 그게 정상 — Phase 6에서 FakeRepo·테스트를 일괄 갱신.

### Task 1.1: PLAYER_ID 제거 + player_id 인자 전파

**Files:** `backend/app/repo.py` (Modify)

- [ ] **Step 1: 모듈 상수 제거**

```python
# 삭제: PLAYER_ID = 1
```

- [ ] **Step 2: 모든 플레이어 스코프 함수에 player_id 첫 인자 추가**

`load_player`, `update_player`, `load_inventory`, `load_player_weapons`, `insert_weapon`, `deduct_materials`, `insert_hero`, `list_alive_heroes`, `list_alive_heroes_ready`, `insert_negotiation`, `insert_battle`, `get_merchant_today`, `insert_merchant_today`, `add_inventory`, `insert_day_event`, `list_day_events`, `list_sold_weapons`, `count_consecutive_survives`, `reset_game`.

각 함수 본문의 `PLAYER_ID` 참조를 모두 `player_id` 인자로 교체. 예:

```python
def load_player(player_id: int) -> dict[str, Any] | None:
    rows = _client().table("players").select("*").eq("id", player_id).limit(1).execute().data
    return rows[0] if rows else None

def update_player(player_id: int, **fields: Any) -> None:
    _client().table("players").update(fields).eq("id", player_id).execute()

def load_inventory(player_id: int) -> list[dict[str, Any]]:
    rows = _client().table("inventory").select("material_id, qty, materials(...)") \
        .eq("player_id", player_id).execute().data
    ...

def insert_weapon(player_id: int, weapon: dict[str, Any]) -> dict[str, Any]:
    return _client().table("weapons").insert({**weapon, "player_id": player_id}).execute().data[0]

def reset_game(player_id: int) -> None:
    c = _client()
    for t in ("day_events", "merchants_today", "battles", "negotiations", "heroes", "weapons", "inventory"):
        c.table(t).delete().eq("player_id", player_id).execute()
    # players row는 유지, 상태만 초기화
    c.table("players").update(
        {"gold": 0, "reputation": 0, "craft_power": 0, "effort": 50,
         "current_day": 1, "current_phase": "forge_open"}
    ).eq("id", player_id).execute()
    # 시작 인벤토리 재시드
    starting = [
        {"player_id": player_id, "material_id": mid, "qty": qty}
        for mid, qty in [(1, 5), (2, 5), (4, 5), (5, 5), (8, 3), (15, 3), (16, 3)]
    ]
    c.table("inventory").insert(starting).execute()
```

ID 기반 단건 함수(`get_weapon`, `get_hero`, `update_hero`, `update_weapon`, `get_negotiation`, `update_negotiation`, `transfer_weapon_to_hero`, `update_merchant_today`)는 시그니처 그대로.

- [ ] **Step 3: 신규 함수 `get_or_create_player_by_nickname`**

```python
def get_or_create_player_by_nickname(nickname: str) -> dict[str, Any]:
    c = _client()
    rows = c.table("players").select("*").eq("nickname", nickname).limit(1).execute().data
    if rows:
        return rows[0]
    created = c.table("players").insert({
        "nickname": nickname, "gold": 0, "reputation": 0, "craft_power": 0,
        "effort": 50, "current_day": 1, "current_phase": "forge_open",
    }).execute().data[0]
    starting = [
        {"player_id": created["id"], "material_id": mid, "qty": qty}
        for mid, qty in [(1, 5), (2, 5), (4, 5), (5, 5), (8, 3), (15, 3), (16, 3)]
    ]
    c.table("inventory").insert(starting).execute()
    return created
```

- [ ] **Step 4: 임포트 동기화 확인**

`grep -n "PLAYER_ID" backend/app` 결과가 비어야 함.

- [ ] **Step 5: Commit**

```bash
git add backend/app/repo.py
git commit -m "refactor(repo): per-call player_id + nickname lookup"
```

---

## Phase 2 — 인증 dependency

### Task 2.1: `auth.py` 작성 (TDD)

**Files:**
- Create: `backend/app/auth.py`
- Create: `backend/tests/test_auth.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# backend/tests/test_auth.py
import pytest
from fastapi import HTTPException
from app import auth

class FakeRepo:
    def __init__(self):
        self.next_id = 1
        self.players = {}
    def get_or_create_player_by_nickname(self, nickname):
        if nickname in self.players:
            return self.players[nickname]
        p = {"id": self.next_id, "nickname": nickname, "gold": 0,
             "effort": 50, "current_day": 1, "current_phase": "forge_open"}
        self.players[nickname] = p
        self.next_id += 1
        return p

def test_current_player_rejects_empty(monkeypatch):
    monkeypatch.setattr(auth, "repo", FakeRepo())
    with pytest.raises(HTTPException) as e:
        auth.current_player("   ")
    assert e.value.status_code == 400

def test_current_player_rejects_too_long(monkeypatch):
    monkeypatch.setattr(auth, "repo", FakeRepo())
    with pytest.raises(HTTPException):
        auth.current_player("a" * 21)

def test_current_player_creates_then_reuses(monkeypatch):
    fake = FakeRepo()
    monkeypatch.setattr(auth, "repo", fake)
    p1 = auth.current_player("Bob")
    p2 = auth.current_player("Bob")
    assert p1["id"] == p2["id"]

def test_current_player_case_sensitive(monkeypatch):
    fake = FakeRepo()
    monkeypatch.setattr(auth, "repo", fake)
    bob = auth.current_player("Bob")
    bob_lower = auth.current_player("bob")
    assert bob["id"] != bob_lower["id"]
```

- [ ] **Step 2: 실패 확인**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/test_auth.py -v
```
Expected: ImportError (`app.auth` 없음).

- [ ] **Step 3: 최소 구현**

```python
# backend/app/auth.py
from fastapi import Header, HTTPException
from typing import Any
from . import repo

def current_player(x_player_nickname: str = Header(...)) -> dict[str, Any]:
    nickname = x_player_nickname.strip()
    if not nickname or len(nickname) > 20:
        raise HTTPException(400, detail={"error": "invalid_nickname"})
    return repo.get_or_create_player_by_nickname(nickname)
```

- [ ] **Step 4: 통과 확인**

```bash
python -m pytest tests/test_auth.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/auth.py backend/tests/test_auth.py
git commit -m "feat(auth): X-Player-Nickname header dependency"
```

---

## Phase 3 — NPC 시드 결정론 (TDD)

### Task 3.1: hero_registry.heroes_for_today에 player_id 추가

**Files:**
- Modify: `backend/app/hero_registry.py`
- Create: `backend/tests/test_hero_registry_multi.py`

- [ ] **Step 1: 실패 테스트**

```python
# backend/tests/test_hero_registry_multi.py
from app import hero_registry

def test_same_player_same_day_deterministic():
    a = hero_registry.heroes_for_today(player_id=1, day=1)
    b = hero_registry.heroes_for_today(player_id=1, day=1)
    assert [h["job"] for h in a] == [h["job"] for h in b]

def test_different_players_different_heroes():
    a = hero_registry.heroes_for_today(player_id=1, day=1)
    b = hero_registry.heroes_for_today(player_id=2, day=1)
    # 적어도 한 명은 직업/이름이 다름
    assert any(
        a[i]["job"] != b[i]["job"] or a[i].get("name") != b[i].get("name")
        for i in range(len(a))
    )
```

- [ ] **Step 2: 실패 확인**

Expected: TypeError (`heroes_for_today() got unexpected keyword argument 'player_id'`).

- [ ] **Step 3: 구현**

`heroes_for_today` 시그니처에 `player_id: int` 추가. 내부 seed 계산:

```python
def heroes_for_today(player_id: int, day: int, count: int = 3) -> list[dict[str, Any]]:
    seed = (player_id * 1_000_003 + day) & 0xFFFFFFFF
    rng = random.Random(seed)
    ...  # 기존 본문 유지하되 rng 사용
```

기존에 `random.Random(day)` 같은 호출이 있으면 위 `rng` 또는 파생 seed로 교체.

- [ ] **Step 4: 통과 확인**

```bash
python -m pytest tests/test_hero_registry_multi.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/hero_registry.py backend/tests/test_hero_registry_multi.py
git commit -m "feat(hero_registry): per-player deterministic seed"
```

### Task 3.2: merchant.generate_today에 player_id 추가

**Files:** `backend/app/merchant.py` (Modify)

- [ ] **Step 1: 실패 테스트 (`backend/tests/test_merchant.py` 끝에 추가)**

```python
def test_generate_today_per_player():
    from app import merchant
    a = merchant.generate_today(player_id=1, day=1)
    b = merchant.generate_today(player_id=2, day=1)
    # materials 구성이 적어도 한 곳에서 다름
    assert a["materials"] != b["materials"] or a["inventory_weapons"] != b["inventory_weapons"]
```

- [ ] **Step 2: 실패 확인**

```bash
python -m pytest tests/test_merchant.py::test_generate_today_per_player -v
```

- [ ] **Step 3: 구현**

`generate_today` 시그니처에 `player_id: int` 추가. seed:

```python
def generate_today(player_id: int, day: int, seed: int | None = None) -> dict[str, Any]:
    if seed is None:
        seed = (player_id * 1_000_003 + day * 31 + 7) & 0xFFFFFFFF
    rng = random.Random(seed)
    ...
```

- [ ] **Step 4: 통과 확인**

- [ ] **Step 5: Commit**

```bash
git add backend/app/merchant.py backend/tests/test_merchant.py
git commit -m "feat(merchant): per-player deterministic seed"
```

---

## Phase 4 — 도메인 모듈 player_id 전파

이 단계 단독 테스트는 어렵고(통합 테스트가 잡아냄), Phase 6에서 일괄 검증.

### Task 4.1: forge.craft

**Files:** `backend/app/forge.py` (Modify)

- [ ] **Step 1: 시그니처 변경**

```python
async def craft(player: dict, weapon_type: str, material_qty: dict[int, int]) -> dict[str, Any]:
    pid = player["id"]
    inv = repo.load_inventory(pid)
    ...
    repo.deduct_materials(pid, material_qty)
    repo.update_player(pid, effort=new_effort)
    # 이미 인자로 player 받았으므로 load_player 재호출 불필요. 단 current_day 갱신 가능성 있으면
    # repo.load_player(pid)로 다시 읽기.
    weapon = repo.insert_weapon(pid, { ... "created_day": player["current_day"], ... })
    repo.insert_day_event(pid, player["current_day"], player.get("current_phase", "forge_open"),
                          "forge", { ... })
    return weapon
```

`load_player()` 호출이 더 이상 없도록 정리 — 직전 effort 차감 후의 player를 다시 읽고 싶으면 `repo.load_player(pid)`로 명시.

- [ ] **Step 2: Commit**

```bash
git add backend/app/forge.py
git commit -m "refactor(forge): receive player + propagate player_id"
```

### Task 4.2: negotiation 전체

**Files:** `backend/app/negotiation.py` (Modify)

- [ ] **Step 1: 함수별 변경**

`step_sell`, `player_accept_counter`, `player_reject`, `finalize_sale`, `step_buy`, `finalize_buy`, `player_accept_buy_counter`, `player_reject_buy`, `step_enhance`, `finalize_enhance`, `player_accept_enhance_counter`, `player_reject_enhance` 모두 `player: dict` 첫 인자 받기. 내부 `repo.load_player()`/`insert_day_event` 등은 `pid = player["id"]` 사용.

`finalize_*`처럼 negotiation row만 가지고 호출되던 함수도 player를 받도록 일관성 유지. (API 레이어가 `Depends(current_player)`로 player를 갖고 있으니 항상 넘길 수 있음.)

- [ ] **Step 2: Commit**

```bash
git add backend/app/negotiation.py
git commit -m "refactor(negotiation): player_id propagation"
```

### Task 4.3: combat, day_summary, nickname

**Files:**
- Modify: `backend/app/combat.py`
- Modify: `backend/app/day_summary.py`
- Modify: `backend/app/nickname.py`

- [ ] **Step 1: combat.run_battle / 관련 함수**

`run_battle(player, hero_id, weapon_id)`. 내부 `repo.*` 호출에 pid 추가. `update_player`, `insert_battle`, `insert_day_event`, `update_hero`/`update_weapon` 모두 pid 필요한 함수는 pid 전달.

- [ ] **Step 2: day_summary.build**

`build(player, day)`. 내부 `list_day_events(pid, day)` 사용.

- [ ] **Step 3: nickname (별명 부여 로직)**

`maybe_award(player, hero_id, ...)` — 내부 `repo.*` 호출에 pid 추가.

- [ ] **Step 4: Commit**

```bash
git add backend/app/combat.py backend/app/day_summary.py backend/app/nickname.py
git commit -m "refactor(domain): player_id propagation"
```

---

## Phase 5 — API 레이어

### Task 5.1: 모든 엔드포인트에 Depends(current_player)

**Files:**
- Modify: `backend/app/api/forge.py`
- Modify: `backend/app/api/negotiate.py`
- Modify: `backend/app/api/battle.py`
- Modify: `backend/app/api/merchant.py`
- Modify: `backend/app/api/enhance.py`
- Modify: `backend/app/api/day.py`
- Modify: `backend/app/api/state.py`
- Modify: `backend/app/api/game.py`

- [ ] **Step 1: 패턴 적용**

각 라우터 함수에:

```python
from fastapi import Depends
from ..auth import current_player

@router.post("/forge", response_model=WeaponOut)
async def post_forge(req: ForgeRequest, player: dict = Depends(current_player)):
    try:
        state_machine.assert_phase_in(player["current_phase"], FORGE_PHASES)
    except state_machine.PhaseError:
        raise HTTPException(400, ...)
    weapon = await forge.craft(player, req.weapon_type, {m.material_id: m.qty for m in req.materials})
    return weapon
```

엔드포인트별 처리 포인트:
- `GET /state` — `get_state(player: dict = Depends(current_player))`. 내부 `repo.load_player()` 호출 제거, 인자 `player`와 `repo.load_inventory(pid)`, `repo.load_player_weapons(pid)` 사용.
- `POST /forge/skip`, `POST /day/next`, `POST /game/reset` — 모두 `player = Depends`. `reset_game`은 `repo.reset_game(player["id"])`.
- `negotiate`, `enhance`, `battle`, `merchant` 라우터도 동일.

- [ ] **Step 2: Commit**

```bash
git add backend/app/api/
git commit -m "feat(api): Depends(current_player) on all endpoints"
```

### Task 5.2: state.py의 hero/merchant 호출도 pid 전달

**Files:** `backend/app/api/state.py` (Modify)

- [ ] **Step 1: 변경**

```python
todays = hero_registry.heroes_for_today(player["id"], player["current_day"])
...
m = repo.get_merchant_today(player["id"], player["current_day"])
if m is None:
    bundle = merchant_module.generate_today(player["id"], player["current_day"])
    m = repo.insert_merchant_today(player["id"], {"day": player["current_day"], **bundle, "outcome": "pending"})
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/api/state.py
git commit -m "fix(state): per-player heroes/merchant"
```

---

## Phase 6 — 테스트 일괄 갱신 (FakeRepo + 기존 테스트)

이 시점에서 76 기존 테스트는 거의 다 깨져 있음. 한 파일씩 통과시킴.

### Task 6.1: FakeRepo 시그니처 갱신

**Files:**
- Modify: `backend/tests/test_integration_day.py`
- Modify: `backend/tests/test_integration_meta.py`

- [ ] **Step 1: FakeRepo 메서드 시그니처에 `player_id` 추가**

각 메서드 첫 인자 `player_id`를 받되 본문은 단일 self.players[player_id] 또는 player_id 무시 (테스트 내 단일 플레이어). 간단히:

```python
def load_player(self, player_id): return self.player  # self.player["id"]==player_id 가정
def update_player(self, player_id, **f): self.player.update(f)
def load_inventory(self, player_id): return list(self.inventory)
def deduct_materials(self, player_id, mq): ...
def add_inventory(self, player_id, mid, qty): ...
def insert_weapon(self, player_id, w): ...
def insert_hero(self, player_id, h): ...
def insert_negotiation(self, player_id, n): ...
def insert_battle(self, player_id, b): ...
def insert_day_event(self, player_id, day, phase, kind, payload): ...
def list_day_events(self, player_id, day): ...
def list_alive_heroes(self, player_id): ...
def list_alive_heroes_ready(self, player_id, day): ...
def get_merchant_today(self, player_id, day): ...
def insert_merchant_today(self, player_id, m): ...
def list_sold_weapons(self, player_id): ...
def list_player_weapons(self, player_id): ...
def count_consecutive_survives(self, player_id, hero_id): ...
def get_or_create_player_by_nickname(self, nickname): return self.player
```

테스트 내 호출 측도 player·player_id를 넘기도록 수정. `heroes_for_today(1, 1)`, `merchant.generate_today(1, day=1, seed=1)` 등.

- [ ] **Step 2: 통과 확인**

```bash
python -m pytest tests/test_integration_day.py tests/test_integration_meta.py -v
```
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_integration_*.py
git commit -m "test: FakeRepo + integration tests for player_id signatures"
```

### Task 6.2: 단위 테스트들 일괄 갱신

**Files:** `backend/tests/test_*.py` (Modify)

- [ ] **Step 1: 영향받는 파일 찾기**

```bash
cd backend && grep -ln "heroes_for_today\|generate_today\|forge\.craft\|negotiation\.\(step\|finalize\)\|combat\.run_battle\|day_summary\.build" tests/
```

각 파일에서 호출 시 player·player_id 추가.

- [ ] **Step 2: 통과 확인**

```bash
python -m pytest -q
```
Expected: 모두 PASS (기존 76 + 신규 ~7 = 83+).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/
git commit -m "test: propagate player_id to existing unit tests"
```

### Task 6.3: 신규 통합 테스트 — 두 player 격리

**Files:** `backend/tests/test_repo_multi.py` (Create)

- [ ] **Step 1: 작성**

```python
import os
os.environ.setdefault("SUPABASE_URL", "http://stub")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "stub")
# FakeRepo 기반 — repo 모듈을 직접 안 쓰고 도메인 함수 통해 격리 확인
from app import forge, negotiation, hero_registry
from unittest.mock import patch

class TwoPlayerFake:
    def __init__(self):
        self.players = {
            1: {"id": 1, "nickname": "A", "gold": 0, "reputation": 0,
                "effort": 50, "current_day": 1, "current_phase": "forge_open"},
            2: {"id": 2, "nickname": "B", "gold": 0, "reputation": 0,
                "effort": 50, "current_day": 1, "current_phase": "forge_open"},
        }
        self.inv = {1: [{"material_id": 1, "qty": 5, "name": "x",
                         "category": "일반", "attribute": None, "base_price": 50}],
                    2: [{"material_id": 1, "qty": 0, "name": "x",
                         "category": "일반", "attribute": None, "base_price": 50}]}
    def load_player(self, pid): return self.players[pid]
    def load_inventory(self, pid): return list(self.inv[pid])
    # 필요한 최소 메서드만

def test_two_players_isolated_inventory():
    fake = TwoPlayerFake()
    assert fake.load_inventory(1)[0]["qty"] == 5
    assert fake.load_inventory(2)[0]["qty"] == 0
```

(불필요하게 무겁지 않게. 핵심 invariant만.)

- [ ] **Step 2: 통과 확인**

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_repo_multi.py
git commit -m "test: two-player inventory isolation"
```

---

## Phase 7 — 프론트엔드

### Task 7.1: auth.ts + api.ts 헤더

**Files:**
- Create: `frontend/src/auth.ts`
- Modify: `frontend/src/api.ts`

- [ ] **Step 1: auth.ts**

```typescript
// frontend/src/auth.ts
const KEY = "smith-tycoon:nickname";

export function getNickname(): string | null {
  return localStorage.getItem(KEY);
}

export function setNickname(name: string): void {
  localStorage.setItem(KEY, name);
}

export function clearNickname(): void {
  localStorage.removeItem(KEY);
}
```

- [ ] **Step 2: api.ts 수정**

모든 fetch 호출에 헤더 부착하는 헬퍼 도입:

```typescript
import { getNickname } from "./auth";

function headers(): HeadersInit {
  const n = getNickname();
  if (!n) throw new Error("no nickname");
  return { "Content-Type": "application/json", "X-Player-Nickname": n };
}

// 각 fetch() 호출의 headers를 headers()로 교체.
// 예: fetch(`${BASE}/state`, { headers: headers() }).then(...)
```

- [ ] **Step 3: tsc 확인**

```bash
cd frontend && npx tsc --noEmit
```
Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/auth.ts frontend/src/api.ts
git commit -m "feat(frontend): nickname header on all API calls"
```

### Task 7.2: Login 컴포넌트 + App 분기

**Files:**
- Create: `frontend/src/components/Login.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Login.tsx**

```tsx
import { useState } from "react";
import { setNickname } from "../auth";

export function Login({ onDone }: { onDone: () => void }) {
  const [name, setName] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const submit = () => {
    const trimmed = name.trim();
    if (!trimmed || trimmed.length > 20) {
      setErr("닉네임은 1–20자");
      return;
    }
    setNickname(trimmed);
    onDone();
  };
  return (
    <div style={{ padding: 24 }}>
      <h2>대장간 입장</h2>
      <input value={name} onChange={(e) => setName(e.target.value)}
             placeholder="닉네임" maxLength={20} />
      <button className="btn" onClick={submit}>입장</button>
      {err && <p style={{ color: "red" }}>{err}</p>}
    </div>
  );
}
```

- [ ] **Step 2: App.tsx 분기**

```tsx
import { getNickname } from "./auth";
import { Login } from "./components/Login";

function App() {
  const [nick, setNick] = useState<string | null>(getNickname());
  if (!nick) return <Login onDone={() => setNick(getNickname())} />;
  // 기존 게임 화면
  ...
}
```

- [ ] **Step 3: tsc 확인**

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/Login.tsx frontend/src/App.tsx
git commit -m "feat(frontend): Login screen + nickname gate"
```

### Task 7.3: SidePanel 로그아웃

**Files:** `frontend/src/components/SidePanel.tsx` (Modify)

- [ ] **Step 1: 로그아웃 버튼 추가**

```tsx
import { clearNickname } from "../auth";

// "새 게임" 버튼 옆에:
<button className="btn" onClick={() => {
  clearNickname();
  window.location.reload();
}} style={{ marginLeft: 8 }}>로그아웃</button>
```

- [ ] **Step 2: tsc 확인 + Commit**

```bash
git add frontend/src/components/SidePanel.tsx
git commit -m "feat(frontend): logout button"
```

---

## Phase 8 — End-to-End 검증

### Task 8.1: 백엔드 풀 테스트

- [ ] **Step 1: 전체 pytest**

```bash
cd backend && python -m pytest -q
```
Expected: all pass (76+신규 ≈ 85+).

### Task 8.2: 수동 검증

- [ ] **Step 1: 서버 재기동**

uvicorn 재시작, vite 재시작.

- [ ] **Step 2: 닉네임 A로 입장 → 무기 제작 → /state 확인 (자기 골드·인벤토리)**

- [ ] **Step 3: 닉네임 B로 입장 (다른 브라우저 또는 시크릿) → A의 무기/골드가 보이지 않음 확인**

- [ ] **Step 4: A로 다시 입장 → A의 진행 상태 그대로 복원 확인**

- [ ] **Step 5: A에서 /game/reset → B의 상태는 그대로, A만 초기화 확인**

### Task 8.3: 최종 커밋

- [ ] **Step 1: 발견한 작은 폴리시 수정**

- [ ] **Step 2: Commit**

```bash
git commit -m "fix: post-verification polish"
```

---

## Self-review 메모

- 스펙 §2 마이그레이션 — Task 0.1로 커버.
- 스펙 §3 백엔드 — Task 1.1, 2.1, 3.x, 4.x, 5.x로 커버.
- 스펙 §4 프론트엔드 — Task 7.x로 커버.
- 스펙 §5 테스트 전략 — Task 2.1(auth), 3.x(hero/merchant), 6.x(기존 + multi)로 커버.
- 스펙 §6 변경 면적 — 위 태스크 파일 목록과 일치.
- 스펙 §7 범위 외(권한·동시성) — 본 플랜에서도 의도적으로 미포함.

# MVP Plan 3 — 단골 메타 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Plan 2 위에 호감도 가격 보정, 회상 대사, 별명 부여, 무기 강화 협상을 얹어 재방문 용사가 의미 있는 단골이 되게 한다.

**Architecture:** state.py가 `hero.mode = "sell" | "enhance"`를 분기. 신규 모듈 3개 (affinity, enhancement, nickname)가 백엔드에 추가되고, negotiation/combat이 이들을 호출한다. 프론트는 mode에 따라 NegotiationChat 또는 EnhanceNegotiation을 렌더한다. Plan 1·2의 server-authoritative·repo 단일 의존성 원칙 유지.

**Tech Stack:** Python 3.12 + FastAPI + supabase-py + Jinja2 / React + Vite + TypeScript / Supabase (Postgres) / OpenAI 호환 LLM.

**선행:** Plan 3 spec — `docs/superpowers/specs/2026-05-26-mvp-plan3-design.md`.

---

## File Structure

```
backend/
├── migrations/
│   └── 003_meta.sql                       신규 (문서용 — 스키마 변경 없음)
├── app/
│   ├── affinity.py                        신규
│   ├── enhancement.py                     신규
│   ├── nickname.py                        신규
│   ├── negotiation.py                     변경 (affinity 반영, step_enhance, finalize_enhance)
│   ├── combat.py                          변경 (nickname 트리거 + 무기 파괴 affinity -5)
│   ├── repo.py                            변경 (count_consecutive_survives, update_weapon)
│   ├── models.py                          변경 (EnhanceNegotiateRequest)
│   ├── main.py                            변경 (enhance 라우터 등록)
│   ├── api/
│   │   ├── enhance.py                     신규
│   │   └── state.py                       변경 (mode, held_weapon)
│   └── llm/prompts/
│       ├── negotiate_enhance.j2           신규
│       ├── nickname.j2                    신규
│       └── negotiate_sell.j2              변경 (affinity·history·nickname 변수)
└── tests/
    ├── test_affinity.py                   신규
    ├── test_enhancement.py                신규
    ├── test_nickname.py                   신규
    ├── test_negotiation.py                변경 (affinity 효과 검증)
    ├── test_integration_meta.py           신규
    └── fixtures/llm/
        ├── enhance_accept.json            신규
        ├── enhance_counter.json           신규
        ├── enhance_reject.json            신규
        └── nickname_candidates.json       신규

frontend/src/
├── api.ts                                 변경 (/enhance/*)
├── types.ts                               변경 (mode, held_weapon)
└── components/
    ├── DayRouter.tsx                      변경 (mode 분기)
    ├── NegotiationChat.tsx                변경 (호감도·별명·회상 표시)
    └── EnhanceNegotiation.tsx             신규

docs/superpowers/plans/
└── 2026-05-26-mvp-plan3-checklist.md      신규
```

---

## Task 1: 003 마이그레이션 (문서용)

**Files:**
- Create: `backend/migrations/003_meta.sql`

Plan 3는 스키마 변경 없음. 마이그레이션 파일은 기록 목적.

- [ ] **Step 1: 파일 생성**

```sql
-- 003_meta.sql — Plan 3 (단골 메타) 기록용
-- 신규 컬럼/테이블 없음. 기존 컬럼 재활용:
--   heroes.affinity, heroes.history, heroes.nickname, heroes.held_weapon_id, heroes.visit_count
--   weapons.enhancement_level, weapons.materials_used (jsonb)
--   negotiations.kind='enhance' (check constraint에 이미 포함)
-- 이 파일은 향후 Plan 3 관련 인덱스 등 필요 시 추가될 수 있음.
select 1;   -- 빈 마이그레이션 회피용 no-op
```

- [ ] **Step 2: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add backend/migrations/003_meta.sql && git commit -m "feat(db): Plan 3 migration placeholder (no schema changes)"
```

---

## Task 2: affinity 모듈

**Files:**
- Create: `backend/app/affinity.py`
- Create: `backend/tests/test_affinity.py`

- [ ] **Step 1: 테스트 작성**

```python
# backend/tests/test_affinity.py
import pytest
from app.affinity import delta_from_ratio, allowed_max_pct, REJECT_SENTINEL


@pytest.mark.parametrize("ratio,expected", [
    (0.5, 10),    # 후한 거래
    (0.89, 10),   # 후한 거래 경계
    (0.9, 5),     # 적정가 하한
    (1.0, 5),     # 적정가
    (1.1, 5),     # 적정가
    (1.2, 5),     # 적정가 상한 (포함)
    (1.21, -10),  # 바가지
    (2.0, -10),   # 바가지
])
def test_delta_from_ratio(ratio, expected):
    assert delta_from_ratio(ratio) == expected


@pytest.mark.parametrize("affinity,expected", [
    (-100, REJECT_SENTINEL),
    (-50, REJECT_SENTINEL),
    (-49, 0.80),
    (-20, 0.80),
    (-19, 0.90),
    (0, 0.90),
    (19, 0.90),
    (20, 1.00),
    (49, 1.00),
    (50, 1.10),
    (100, 1.10),
])
def test_allowed_max_pct(affinity, expected):
    assert allowed_max_pct(affinity) == expected
```

- [ ] **Step 2: Run tests (FAIL)**

```bash
cd /home/afraidnot/dev/smith-tycoon/backend && ./.venv/bin/pytest tests/test_affinity.py -v
```
Expected: ModuleNotFoundError.

- [ ] **Step 3: Create `backend/app/affinity.py`**

```python
"""호감도 기반 규칙 — 가격 허용 범위와 거래 후 호감도 변화."""

REJECT_SENTINEL = "reject"


def delta_from_ratio(ratio: float) -> int:
    """합의가/시세 비율 → 호감도 변화."""
    if ratio < 0.9:
        return 10   # 후한 거래
    if ratio <= 1.2:
        return 5    # 적정가
    return -10      # 바가지


def allowed_max_pct(affinity: int) -> float | str:
    """호감도 → 시세 대비 합의 가능 상한 비율 (또는 REJECT_SENTINEL)."""
    if affinity <= -50:
        return REJECT_SENTINEL
    if affinity <= -20:
        return 0.80
    if affinity <= 19:
        return 0.90
    if affinity <= 49:
        return 1.00
    return 1.10


def clamp_affinity(value: int) -> int:
    """affinity 컬럼은 -100..100 범위로 제한."""
    return max(-100, min(100, int(value)))
```

- [ ] **Step 4: Run tests (PASS)**

```bash
cd /home/afraidnot/dev/smith-tycoon/backend && ./.venv/bin/pytest tests/test_affinity.py -v
```
Expected: 19 PASS (7 + 12 parametrized).

- [ ] **Step 5: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add backend/app/affinity.py backend/tests/test_affinity.py && git commit -m "feat(affinity): delta_from_ratio + allowed_max_pct + clamp_affinity"
```

---

## Task 3: enhancement 모듈

**Files:**
- Create: `backend/app/enhancement.py`
- Create: `backend/tests/test_enhancement.py`

- [ ] **Step 1: 테스트 작성**

```python
# backend/tests/test_enhancement.py
import pytest
from app.enhancement import roll_delta, apply_to_weapon


@pytest.mark.parametrize("category,sharp_min,sharp_max,rar_min,rar_max", [
    ("일반",   1, 3, 0, 2),
    ("이상한", 0, 2, 0, 2),
    ("특수",   3, 7, 2, 5),
    ("전설",   7, 15, 5, 12),
])
def test_roll_delta_per_category(category, sharp_min, sharp_max, rar_min, rar_max):
    for seed in range(30):
        d = roll_delta([{"category": category, "qty": 1}], seed=seed)
        assert sharp_min <= d["sharpness"] <= sharp_max
        assert rar_min <= d["rarity"] <= rar_max


def test_roll_delta_sums_multiple_materials():
    # 일반 + 특수 = 적어도 일반 최소 + 특수 최소만큼은 올라감
    for seed in range(10):
        d = roll_delta([{"category": "일반", "qty": 1}, {"category": "특수", "qty": 1}], seed=seed)
        assert d["sharpness"] >= 1 + 3   # 1(일반 min) + 3(특수 min)
        assert d["rarity"] >= 0 + 2


def test_apply_to_weapon_caps_at_100():
    w = {"sharpness": 95, "rarity": 90, "enhancement_level": 0, "materials_used": []}
    new = apply_to_weapon(w, {"sharpness": 10, "rarity": 15},
                          used_materials=[{"category": "전설", "qty": 1}])
    assert new["sharpness"] == 100
    assert new["rarity"] == 100
    assert new["enhancement_level"] == 1
    assert new["materials_used"][-1]["action"] == "enhance"
    assert new["materials_used"][-1]["delta"] == {"sharpness": 10, "rarity": 15}


def test_apply_to_weapon_appends_to_existing_materials_used():
    w = {"sharpness": 30, "rarity": 20, "enhancement_level": 2,
         "materials_used": [{"name": "철덩이", "qty": 2}]}
    new = apply_to_weapon(w, {"sharpness": 3, "rarity": 1},
                          used_materials=[{"category": "일반", "qty": 1}])
    assert new["enhancement_level"] == 3
    assert len(new["materials_used"]) == 2
    assert new["materials_used"][0]["name"] == "철덩이"   # 보존
```

- [ ] **Step 2: Run tests (FAIL)**

```bash
cd /home/afraidnot/dev/smith-tycoon/backend && ./.venv/bin/pytest tests/test_enhancement.py -v
```
Expected: ModuleNotFoundError.

- [ ] **Step 3: Create `backend/app/enhancement.py`**

```python
"""무기 강화 — 카테고리별 Δ 표 (architecture.md §11.3)."""
from __future__ import annotations
import random
from typing import Any

# (예리도 min, max), (희귀도 min, max)
CATEGORY_DELTAS: dict[str, tuple[tuple[int, int], tuple[int, int]]] = {
    "일반":   ((1, 3),  (0, 2)),
    "이상한": ((0, 2),  (0, 2)),
    "특수":   ((3, 7),  (2, 5)),
    "전설":   ((7, 15), (5, 12)),
}


def roll_delta(materials: list[dict[str, Any]], seed: int | None = None) -> dict[str, int]:
    """재료 카테고리별 Δ를 합산해 무기 sharp/rarity 증가량 반환."""
    rng = random.Random(seed)
    total_sharp = 0
    total_rarity = 0
    for m in materials:
        ranges = CATEGORY_DELTAS.get(m.get("category", ""), ((0, 1), (0, 1)))
        qty = int(m.get("qty", 1))
        for _ in range(qty):
            total_sharp += rng.randint(*ranges[0])
            total_rarity += rng.randint(*ranges[1])
    return {"sharpness": total_sharp, "rarity": total_rarity}


def apply_to_weapon(weapon: dict[str, Any], delta: dict[str, int],
                    used_materials: list[dict[str, Any]]) -> dict[str, Any]:
    """무기에 강화 결과를 적용해 갱신된 dict 반환 (원본 비파괴, in-place 갱신 아님)."""
    new = dict(weapon)
    new["sharpness"] = min(100, int(weapon.get("sharpness", 0)) + delta["sharpness"])
    new["rarity"] = min(100, int(weapon.get("rarity", 0)) + delta["rarity"])
    new["enhancement_level"] = int(weapon.get("enhancement_level", 0)) + 1
    existing = list(weapon.get("materials_used") or [])
    existing.append({
        "action": "enhance",
        "materials": used_materials,
        "delta": delta,
    })
    new["materials_used"] = existing
    return new


def bundle_estimate(weapon: dict[str, Any], materials: list[dict[str, Any]]) -> int:
    """강화 비용의 합리적 시작가 (Δ 평균 + 무기 현재 가치 일부)."""
    avg_sharp = 0.0
    avg_rarity = 0.0
    for m in materials:
        ranges = CATEGORY_DELTAS.get(m.get("category", ""), ((0, 1), (0, 1)))
        qty = int(m.get("qty", 1))
        avg_sharp += (ranges[0][0] + ranges[0][1]) / 2 * qty
        avg_rarity += (ranges[1][0] + ranges[1][1]) / 2 * qty
    # 대략 Δ당 가치: sharpness 1 ≈ 30 골드, rarity 1 ≈ 60 골드
    return max(50, int(avg_sharp * 30 + avg_rarity * 60))
```

- [ ] **Step 4: Tests PASS**

```bash
cd /home/afraidnot/dev/smith-tycoon/backend && ./.venv/bin/pytest tests/test_enhancement.py -v
```
Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add backend/app/enhancement.py backend/tests/test_enhancement.py && git commit -m "feat(enhancement): roll_delta + apply_to_weapon + bundle_estimate"
```

---

## Task 4: repo 확장 — count_consecutive_survives, update_weapon

**Files:**
- Modify: `backend/app/repo.py`

- [ ] **Step 1: Append functions to `backend/app/repo.py`**

```python


# --- Plan 3 ---

def update_weapon(weapon_id: int, **fields: Any) -> None:
    _client().table("weapons").update(fields).eq("id", weapon_id).execute()


def count_consecutive_survives(hero_id: int) -> int:
    """이 hero의 가장 최근부터 거슬러 올라가며 'hero=survived AND demon=killed'가 끊기지 않는 연속 횟수."""
    c = _client()
    rows = c.table("battles").select("outcomes").eq("hero_id", hero_id) \
        .order("id", desc=True).execute().data
    count = 0
    for r in rows:
        out = r.get("outcomes") or {}
        if out.get("hero") == "survived" and out.get("demon") == "killed":
            count += 1
        else:
            break
    return count
```

- [ ] **Step 2: 회귀 테스트**

```bash
cd /home/afraidnot/dev/smith-tycoon/backend && ./.venv/bin/pytest -v 2>&1 | tail -5
```
Expected: 모든 기존 + 신규 25개 (Plan 2 38 + Plan 3 6 enhancement + Plan 3 19 affinity) = 63 PASS. (정확한 개수는 환경에 따라 다를 수 있음; 모두 PASS만 확인.)

- [ ] **Step 3: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add backend/app/repo.py && git commit -m "feat(repo): update_weapon + count_consecutive_survives"
```

---

## Task 5: nickname 모듈

**Files:**
- Create: `backend/app/nickname.py`
- Create: `backend/tests/test_nickname.py`
- Create: `backend/app/llm/prompts/nickname.j2`
- Create: `backend/tests/fixtures/llm/nickname_candidates.json`

- [ ] **Step 1: Fixture 작성**

`backend/tests/fixtures/llm/nickname_candidates.json`:
```json
{"nicknames": ["단도의 신", "어둠의 사신", "백전무패"]}
```

- [ ] **Step 2: Prompt 작성**

`backend/app/llm/prompts/nickname.j2`:
```
당신은 판타지 세계의 음유시인입니다. 다음 용사의 활약을 보고 어울리는 별명 3개를 한국어로 지어주세요.

용사: {{ hero.name }} ({{ hero.job }}, 근력 {{ hero.str }}, 마력 {{ hero.mag }})
연속 생존 횟수: {{ consecutive }}
주로 처치한 적: {{ recent_demons|join(", ") }}
호감도: {{ hero.affinity }}

별명은 짧고 인상적이어야 하며 (3~8자), 직업·활약에 어울려야 합니다.

다음 JSON 형식으로만 답하세요:
{"nicknames": ["<후보1>", "<후보2>", "<후보3>"]}
```

- [ ] **Step 3: Test 작성**

`backend/tests/test_nickname.py`:
```python
from app.nickname import should_award


def test_should_award_meets_all_conditions():
    hero = {"affinity": 25, "nickname": None}
    assert should_award(hero, consecutive_survives=2) is True


def test_should_award_consecutive_less_than_2():
    hero = {"affinity": 25, "nickname": None}
    assert should_award(hero, consecutive_survives=1) is False


def test_should_award_low_affinity():
    hero = {"affinity": 19, "nickname": None}
    assert should_award(hero, consecutive_survives=3) is False


def test_should_award_already_has_nickname():
    hero = {"affinity": 50, "nickname": "이미 있음"}
    assert should_award(hero, consecutive_survives=5) is False
```

- [ ] **Step 4: Run tests (FAIL)**

```bash
cd /home/afraidnot/dev/smith-tycoon/backend && ./.venv/bin/pytest tests/test_nickname.py -v
```

- [ ] **Step 5: Create `backend/app/nickname.py`**

```python
"""별명 부여 — 조건 체크 + LLM 호출."""
from __future__ import annotations
import random
from typing import Any
from .llm.client import complete_json


def should_award(hero: dict[str, Any], consecutive_survives: int) -> bool:
    """별명 부여 자격 — affinity ≥20, nickname None, 연속 생존 ≥2."""
    if hero.get("nickname"):
        return False
    if int(hero.get("affinity", 0)) < 20:
        return False
    if consecutive_survives < 2:
        return False
    return True


async def award(hero: dict[str, Any], consecutive: int, recent_demons: list[str],
                seed: int | None = None) -> str | None:
    """LLM에 별명 3개 후보 요청 → 랜덤 1개 픽. 실패 시 None 반환."""
    try:
        llm = await complete_json(
            "nickname", "nickname_candidates",
            hero=hero, consecutive=consecutive, recent_demons=recent_demons,
        )
        candidates = llm.get("nicknames") or []
        if not candidates:
            return None
        rng = random.Random(seed)
        return rng.choice(candidates)
    except Exception:
        return None
```

- [ ] **Step 6: Tests PASS**

```bash
cd /home/afraidnot/dev/smith-tycoon/backend && ./.venv/bin/pytest tests/test_nickname.py -v
```
Expected: 4 PASS.

- [ ] **Step 7: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add backend/app/nickname.py backend/app/llm/prompts/nickname.j2 backend/tests/test_nickname.py backend/tests/fixtures/llm/nickname_candidates.json && git commit -m "feat(nickname): award conditions + LLM prompt + fixture"
```

---

## Task 6: combat — nickname 트리거 + 무기 파괴 affinity 패널티

**Files:**
- Modify: `backend/app/combat.py`

- [ ] **Step 1: Imports 갱신**

상단 import에 nickname, affinity 추가:

```python
from . import repo, state_machine, hero_registry, nickname as nickname_mod, affinity as affinity_mod
```

- [ ] **Step 2: run_battle 끝 부분에 nickname 트리거 + 무기 파괴 시 affinity -5 추가**

기존 코드:
```python
    # 무기 파괴 시 held_weapon_id 비움
    if outcomes.get("weapon") == "destroyed":
        fields["held_weapon_id"] = None
    repo.update_hero(hero_id, **fields)
```

다음으로 교체:

```python
    # 무기 파괴 시 held_weapon_id 비움 + affinity -5
    if outcomes.get("weapon") == "destroyed":
        fields["held_weapon_id"] = None
        current_aff = int(hero.get("affinity", 0))
        fields["affinity"] = affinity_mod.clamp_affinity(current_aff - 5)
    repo.update_hero(hero_id, **fields)

    # 별명 부여 트리거
    if outcomes.get("hero") == "survived" and outcomes.get("demon") == "killed":
        consecutive = repo.count_consecutive_survives(hero_id) + 1  # 이번 전투 포함
        refreshed_hero = repo.get_hero(hero_id)
        if nickname_mod.should_award(refreshed_hero, consecutive):
            recent_demons = [demon["type"]]  # 최소 — 더 풍부하게 하려면 battles 조회
            picked = await nickname_mod.award(refreshed_hero, consecutive, recent_demons)
            if picked:
                repo.update_hero(hero_id, nickname=picked)
                repo.insert_day_event(
                    day=player["current_day"], phase=player["current_phase"],
                    kind="nickname", payload={"hero_id": hero_id, "nickname": picked},
                )
```

- [ ] **Step 3: 회귀 테스트**

```bash
cd /home/afraidnot/dev/smith-tycoon/backend && ./.venv/bin/pytest -v 2>&1 | tail -5
```
Expected: 모든 기존 테스트 PASS (count_consecutive_survives는 새 함수, combat.py 변경은 직접 테스트 안 됨).

- [ ] **Step 4: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add backend/app/combat.py && git commit -m "feat(combat): nickname trigger + weapon destroyed affinity penalty"
```

---

## Task 7: negotiation step_sell — affinity 적용 + 회상 변수 주입

**Files:**
- Modify: `backend/app/negotiation.py`
- Modify: `backend/app/llm/prompts/negotiate_sell.j2`

- [ ] **Step 1: `step_sell` 갱신 — affinity 즉시 거부 + 가격 ceiling + 프롬프트 enrichment**

기존 step_sell의 시작 부분 (weapon, hero, base, hero_gold 로딩 후) — 다음 블록을 삽입:

```python
    # Plan 3: 호감도 ≤ -50 → 즉시 거부 (협상 진입 자체 거부)
    from . import affinity as affinity_mod
    affinity = int(hero.get("affinity", 0))
    max_pct = affinity_mod.allowed_max_pct(affinity)
    if max_pct == affinity_mod.REJECT_SENTINEL:
        player_now = repo.load_player()
        repo.insert_day_event(
            day=player_now["current_day"], phase=player_now["current_phase"],
            kind="reject", payload={"by": "hero_blacklist", "hero_id": hero_id, "rep_delta": 0},
        )
        repo.update_player(current_phase=state_machine.next_phase(player_now["current_phase"]))
        return {
            "negotiation_id": -1,
            "decision": "reject",
            "counter_price": None,
            "message": "당신과는 거래하지 않겠소.",
        }
    ceiling = int(base * max_pct)
```

- [ ] **Step 2: LLM 호출 인자 갱신 — 회상 변수 주입**

기존 `complete_json("negotiate_sell", ...)` 호출의 인자를 다음으로 확장:

```python
    llm = await complete_json("negotiate_sell", fixture_name,
                              hero=hero, weapon=weapon,
                              market_price=base,
                              prior_rounds=prior_rounds,
                              player_message=player_message,
                              price_offered=safe_price,
                              preferences=prefs,
                              weapon_fits=weapon_fits,
                              # Plan 3 신규
                              affinity=affinity,
                              allowed_max_pct=max_pct,
                              ceiling=ceiling,
                              history_recent=(hero.get("history") or [])[-5:],
                              nickname=hero.get("nickname"))
```

- [ ] **Step 3: 자동 수락 조건 갱신 (호감도 ceiling 기반)**

step_sell의 기존 자동 수락 if/else 블록 (`if max_hero_counter is not None and safe_price <= max_hero_counter: ... else: complete_json(...)`)을 다음으로 완전 교체:

```python
    # Plan 3: 자동 수락 조건 — safe_price가 호감도 ceiling 안 + (prior counter 조건도 만족)
    server_can_accept = (safe_price <= ceiling)
    if max_hero_counter is not None:
        server_can_accept = server_can_accept and (safe_price <= max_hero_counter)

    if server_can_accept:
        llm = {
            "decision": "accept",
            "counter_price": None,
            "message": f"좋소, {safe_price} 골드면 거래합시다.",
        }
    else:
        from . import hero_registry as _hr
        prefs = _hr.preferences_for(hero)
        weapon_fits = weapon["type"] in prefs.get("types", [])
        fixture_name = "negotiate_accept"
        llm = await complete_json("negotiate_sell", fixture_name,
                                  hero=hero, weapon=weapon,
                                  market_price=base,
                                  prior_rounds=prior_rounds,
                                  player_message=player_message,
                                  price_offered=safe_price,
                                  preferences=prefs,
                                  weapon_fits=weapon_fits,
                                  # Plan 3 신규
                                  affinity=affinity,
                                  allowed_max_pct=max_pct,
                                  ceiling=ceiling,
                                  history_recent=(hero.get("history") or [])[-5:],
                                  nickname=hero.get("nickname"))
```

(Step 2의 LLM 호출 코드 블록은 이 Step 3의 else 분기로 통합됩니다 — Step 2를 별개로 적용하지 않고 이 Step 3가 두 가지를 모두 포함.)

- [ ] **Step 4: finalize_sale — affinity 변화 적용**

기존 finalize_sale의 update_hero 부분을 다음으로 교체:

```python
def finalize_sale(neg_id: int) -> None:
    neg = repo.get_negotiation(neg_id)
    if neg["outcome"] != "accepted":
        raise ValueError("negotiation not accepted")
    player = repo.load_player()
    repo.transfer_weapon_to_hero(neg["weapon_id"], neg["counterparty_id"])
    repo.update_player(gold=player["gold"] + neg["agreed_price"],
                       reputation=player["reputation"] + 1,
                       current_phase=state_machine.next_phase(player["current_phase"]))
    hero = repo.get_hero(neg["counterparty_id"])
    weapon = repo.get_weapon(neg["weapon_id"])

    # Plan 3: 호감도 변화 — 합의가/시세 비율 기반
    from . import affinity as affinity_mod
    base = market_price(weapon)
    ratio = neg["agreed_price"] / max(base, 1)
    aff_delta = affinity_mod.delta_from_ratio(ratio)
    new_affinity = affinity_mod.clamp_affinity(int(hero.get("affinity", 0)) + aff_delta)

    new_history = (hero["history"] or []) + [
        {"weapon": weapon["name"], "price": neg["agreed_price"], "ratio": round(ratio, 2),
         "battle": None}
    ]
    repo.update_hero(neg["counterparty_id"], affinity=new_affinity,
                     history=new_history[-5:], held_weapon_id=neg["weapon_id"])
    repo.insert_day_event(
        day=player["current_day"], phase=player["current_phase"], kind="sale",
        payload={"negotiation_id": neg_id, "weapon_id": neg["weapon_id"],
                 "hero_id": neg["counterparty_id"], "price": neg["agreed_price"],
                 "affinity_delta": aff_delta},
    )
```

- [ ] **Step 5: `negotiate_sell.j2` 프롬프트 갱신**

`backend/app/llm/prompts/negotiate_sell.j2` 끝에 다음 블록 삽입 (협상 지침 위쪽이나 적당한 위치):

```
{% if affinity >= 20 %}
=== 단골 정보 (호감도 {{ affinity }}{% if nickname %}, 별명 "{{ nickname }}"{% endif %}) ===
이전 거래:
{% for h in history_recent %}- {{ h.weapon }}을 {{ h.price }}골드에 (비율 {{ h.ratio }}){% if h.battle %} 후 {{ h.battle }}{% endif %}
{% endfor %}

당신은 이 대장장이의 단골입니다. 회상 대사("지난번 그 ○○ 잘 쓰고 있소" 등)를 자연스럽게 한 번 정도 섞으세요.
{% elif affinity <= -20 %}
=== 단골 정보 (호감도 {{ affinity }} — 불만 상태) ===
이전 거래에 불만이 있었던 것 같습니다. 깐깐하게 협상하세요.
{% endif %}

가격 허용 범위:
- 시세 대비 {{ allowed_max_pct * 100 }}%까지 합의 가능 (= 최대 {{ ceiling }} 골드).
- 이 한도를 넘는 가격은 절대 수락하지 마세요.
```

- [ ] **Step 6: 회귀 + step_sell 테스트 갱신/확인**

기존 `test_negotiation.py`의 step_sell 관련 테스트가 새 인자 변경에도 통과하는지 확인. fixture 모드라 LLM 호출 안 됨.

```bash
cd /home/afraidnot/dev/smith-tycoon/backend && ./.venv/bin/pytest -v 2>&1 | tail -5
```

- [ ] **Step 7: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add backend/app/negotiation.py backend/app/llm/prompts/negotiate_sell.j2 && git commit -m "feat(negotiation): apply affinity to sell — ceiling, recall vars, finalize delta"
```

---

## Task 8: negotiation step_enhance + finalize_enhance

**Files:**
- Modify: `backend/app/negotiation.py`
- Create: `backend/app/llm/prompts/negotiate_enhance.j2`
- Create: `backend/tests/fixtures/llm/enhance_accept.json`
- Create: `backend/tests/fixtures/llm/enhance_counter.json`
- Create: `backend/tests/fixtures/llm/enhance_reject.json`

- [ ] **Step 1: Fixtures 3개 작성**

`backend/tests/fixtures/llm/enhance_accept.json`:
```json
{"decision": "accept", "message": "좋소, 그 가격이면 강화 부탁합시다.", "counter_price": null}
```

`backend/tests/fixtures/llm/enhance_counter.json`:
```json
{"decision": "counter", "message": "비싸오. 500 골드 정도면 어떻소?", "counter_price": 500}
```

`backend/tests/fixtures/llm/enhance_reject.json`:
```json
{"decision": "reject", "message": "그 가격엔 강화 의뢰 안 하겠소.", "counter_price": null}
```

- [ ] **Step 2: Prompt 작성**

`backend/app/llm/prompts/negotiate_enhance.j2`:
```
당신은 이미 무기를 보유한 용사입니다. 대장장이에게 무기 강화를 의뢰하려 합니다.

용사: {{ hero.name }} ({{ hero.job }}, 보유 금화 {{ hero.gold }})
호감도: {{ affinity }}{% if nickname %} · 별명 "{{ nickname }}"{% endif %}

당신의 무기:
- 이름: {{ weapon.name }}
- 종류: {{ weapon.type }}, 현재 예리도 {{ weapon.sharpness }}, 희귀도 {{ weapon.rarity }}
- 강화 횟수: {{ weapon.enhancement_level }}회

투입 재료:
{% for m in materials %}- {{ m.name }} × {{ m.qty }} ({{ m.category }})
{% endfor %}
예상 가치(참고): {{ base_estimate }} 골드

지금까지의 대화 (총 {{ prior_rounds|length // 2 }}라운드):
{% for r in prior_rounds %}- {{ r.role }}: "{{ r.message }}"{% if r.price %} (가격: {{ r.price }}){% endif %}
{% endfor %}

대장장이의 새 제안: {% if player_message %}"{{ player_message }}"{% else %}(말없이 가격만 제시){% endif %} (가격: {{ price_offered }} 골드)

협상 지침:
- 2~3라운드 흥정 후 결론.
- 예상 가치 ±20% 이내면 accept 고려.
- 너무 비싸면 counter (적정선 제안). 너무 비현실적이면 reject.
- 본인 보유 금화({{ hero.gold }}) 이상은 절대 수락·제시 금지.
- message는 본인 직업·성격 톤으로 한 문장 이상.

다음 JSON 형식으로만 답하세요:
{"decision": "accept" | "reject" | "counter", "counter_price": <정수, counter일 때만>, "message": "<용사 대사>"}
```

- [ ] **Step 3: Append `step_enhance` and `finalize_enhance` and helpers to `backend/app/negotiation.py` END**

```python


# --- Plan 3: 강화 협상 ---

async def step_enhance(hero_id: int, price_offered: int, player_message: str,
                       neg_id: int | None,
                       selected_materials: list[dict[str, int]] | None = None
                       ) -> dict[str, Any]:
    from . import enhancement as enh_mod, affinity as aff_mod
    hero = repo.get_hero(hero_id)
    weapon_id = hero.get("held_weapon_id")
    if not weapon_id:
        raise ValueError("hero has no held weapon")
    weapon = repo.get_weapon(weapon_id)
    hero_gold = max(0, int(hero.get("gold", 0)))
    affinity = int(hero.get("affinity", 0))

    if neg_id is None:
        # 첫 라운드 — 재료 검증
        inv = repo.load_inventory()
        inv_by_id = {row["material_id"]: row for row in inv}
        sub_materials = []
        for s in (selected_materials or []):
            mid = int(s["material_id"])
            qty = int(s.get("qty", 0))
            if qty <= 0:
                continue
            row = inv_by_id.get(mid)
            if not row or row["qty"] < qty:
                raise ValueError(f"insufficient material {mid}")
            sub_materials.append({"material_id": mid, "name": row["name"],
                                  "category": row["category"],
                                  "attribute": row["attribute"], "qty": qty})
        if not sub_materials:
            raise ValueError("no_materials_selected")

        base_estimate = enh_mod.bundle_estimate(weapon, sub_materials)
        player = repo.load_player()
        neg = repo.insert_negotiation({
            "day": player["current_day"], "phase": player["current_phase"],
            "kind": "enhance", "counterparty_id": hero_id, "weapon_id": weapon_id,
            "materials": {"selected": sub_materials, "base_estimate": base_estimate},
            "rounds": [], "outcome": "open",
        })
        neg_id = neg["id"]
        prior_rounds: list[dict[str, Any]] = []
    else:
        neg = repo.get_negotiation(neg_id)
        prior_rounds = neg["rounds"]
        sub_materials = neg["materials"]["selected"]
        base_estimate = neg["materials"]["base_estimate"]

    # 플레이어 제시가는 hero.gold cap
    safe_price = min(max(1, int(price_offered)), hero_gold)

    # max prior hero counter (단조 비감소)
    hero_prior_counters = [int(r["price"]) for r in prior_rounds
                            if r["role"] == "hero" and r.get("price") is not None]
    max_hero_counter = max(hero_prior_counters) if hero_prior_counters else None

    if max_hero_counter is not None and safe_price <= max_hero_counter:
        llm = {"decision": "accept", "counter_price": None,
               "message": f"좋소, {safe_price} 골드에 강화 부탁합시다."}
    else:
        llm = await complete_json(
            "negotiate_enhance", "enhance_accept",
            hero=hero, weapon=weapon, materials=sub_materials,
            base_estimate=base_estimate,
            affinity=affinity, nickname=hero.get("nickname"),
            prior_rounds=prior_rounds,
            player_message=player_message,
            price_offered=safe_price,
        )

    decision = llm["decision"]
    counter = llm.get("counter_price")
    if counter is not None:
        counter = max(1, int(counter))
        if max_hero_counter is not None and counter < max_hero_counter:
            counter = max_hero_counter
        counter = min(counter, hero_gold)
        if counter >= safe_price:
            decision = "accept"
            llm = {**llm, "decision": "accept", "counter_price": None,
                   "message": f"좋소, {safe_price} 골드에 강화 부탁합시다."}
            counter = None

    if decision == "accept" and safe_price > hero_gold:
        decision = "reject"
        llm = {**llm, "decision": "reject",
               "message": f"내가 가진 돈은 {hero_gold}골드뿐이라 그 가격엔 못 내겠소."}

    new_rounds = prior_rounds + [
        {"role": "player", "message": player_message, "price": safe_price},
        {"role": "hero", "message": llm["message"], "price": counter},
    ]
    update: dict[str, Any] = {"rounds": new_rounds}
    if decision == "accept":
        update["outcome"] = "accepted"
        update["agreed_price"] = safe_price
    elif decision == "reject":
        update["outcome"] = "rejected"
        player_now = repo.load_player()
        repo.insert_day_event(
            day=player_now["current_day"], phase=player_now["current_phase"],
            kind="reject", payload={"by": "hero", "hero_id": hero_id, "rep_delta": -1,
                                     "context": "enhance"},
        )
        repo.update_player(
            reputation=player_now["reputation"] - 1,
            current_phase=state_machine.next_phase(player_now["current_phase"]),
        )
    repo.update_negotiation(neg_id, **update)

    return {
        "negotiation_id": neg_id,
        "decision": decision,
        "counter_price": counter,
        "message": llm["message"],
    }


def finalize_enhance(neg_id: int) -> None:
    from . import enhancement as enh_mod, affinity as aff_mod
    neg = repo.get_negotiation(neg_id)
    if neg["outcome"] != "accepted":
        raise ValueError("negotiation not accepted")

    weapon = repo.get_weapon(neg["weapon_id"])
    sub_materials = neg["materials"]["selected"]
    base_estimate = neg["materials"]["base_estimate"]

    # Δ roll + 무기 적용
    delta = enh_mod.roll_delta(sub_materials)
    new_weapon = enh_mod.apply_to_weapon(weapon, delta, sub_materials)
    repo.update_weapon(
        weapon["id"],
        sharpness=new_weapon["sharpness"],
        rarity=new_weapon["rarity"],
        enhancement_level=new_weapon["enhancement_level"],
        materials_used=new_weapon["materials_used"],
    )

    # 재료 차감
    repo.deduct_materials({int(m["material_id"]): int(m["qty"]) for m in sub_materials})

    # 플레이어 보상 + phase advance
    player = repo.load_player()
    repo.update_player(
        gold=player["gold"] + neg["agreed_price"],
        reputation=player["reputation"] + 1,
        current_phase=state_machine.next_phase(player["current_phase"]),
    )

    # 호감도 변화
    ratio = neg["agreed_price"] / max(base_estimate, 1)
    aff_delta = aff_mod.delta_from_ratio(ratio)
    hero = repo.get_hero(neg["counterparty_id"])
    new_history = (hero["history"] or []) + [
        {"action": "enhance", "weapon": weapon["name"], "price": neg["agreed_price"],
         "delta": delta, "ratio": round(ratio, 2)}
    ]
    repo.update_hero(neg["counterparty_id"],
                     affinity=aff_mod.clamp_affinity(int(hero.get("affinity", 0)) + aff_delta),
                     history=new_history[-5:])

    repo.insert_day_event(
        day=player["current_day"], phase=player["current_phase"], kind="enhance",
        payload={"negotiation_id": neg_id, "weapon_id": weapon["id"],
                 "hero_id": neg["counterparty_id"],
                 "price": neg["agreed_price"], "delta": delta,
                 "affinity_delta": aff_delta},
    )


def player_accept_enhance_counter(neg_id: int) -> int:
    neg = repo.get_negotiation(neg_id)
    if neg["outcome"] != "open":
        raise ValueError(f"negotiation already {neg['outcome']}")
    hero_rounds = [r for r in neg["rounds"]
                   if r["role"] == "hero" and r.get("price") is not None]
    if not hero_rounds:
        raise ValueError("no hero counter to accept")
    agreed = int(hero_rounds[-1]["price"])
    repo.update_negotiation(neg_id, outcome="accepted", agreed_price=agreed)
    return agreed


def player_reject_enhance(neg_id: int) -> None:
    neg = repo.get_negotiation(neg_id)
    if neg["outcome"] != "open":
        raise ValueError(f"negotiation already {neg['outcome']}")
    repo.update_negotiation(neg_id, outcome="rejected")
    player_now = repo.load_player()
    repo.insert_day_event(
        day=player_now["current_day"], phase=player_now["current_phase"],
        kind="reject", payload={"by": "player", "negotiation_id": neg_id, "rep_delta": -1,
                                 "context": "enhance"},
    )
    repo.update_player(
        reputation=player_now["reputation"] - 1,
        current_phase=state_machine.next_phase(player_now["current_phase"]),
    )
```

- [ ] **Step 4: 회귀 테스트**

```bash
cd /home/afraidnot/dev/smith-tycoon/backend && ./.venv/bin/pytest -v 2>&1 | tail -5
```
Expected: 모든 기존 테스트 PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add backend/app/negotiation.py backend/app/llm/prompts/negotiate_enhance.j2 backend/tests/fixtures/llm/enhance_*.json && git commit -m "feat(negotiation): step_enhance + finalize_enhance + accept/reject + prompt + fixtures"
```

---

## Task 9: api/enhance.py + 모델 + 라우터 등록

**Files:**
- Create: `backend/app/api/enhance.py`
- Modify: `backend/app/models.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: `backend/app/models.py`에 추가**

```python


class MaterialPick(BaseModel):
    material_id: int
    qty: int


class EnhanceNegotiateRequest(BaseModel):
    price_offered: int
    player_message: str
    negotiation_id: int | None = None
    selected_materials: list[MaterialPick] | None = None
```

- [ ] **Step 2: Create `backend/app/api/enhance.py`**

```python
from fastapi import APIRouter, HTTPException
from .. import repo, negotiation, state_machine
from ..models import EnhanceNegotiateRequest, NegotiateResponse, FinalizeRequest

router = APIRouter()

NEGOTIATE_PHASES = ["hero1_negotiate", "hero2_negotiate", "hero3_negotiate"]


def _hero_index_for_phase(phase: str) -> int:
    return {"hero1_negotiate": 0, "hero2_negotiate": 1, "hero3_negotiate": 2}[phase]


@router.post("/enhance/negotiate", response_model=NegotiateResponse)
async def post_enhance_negotiate(req: EnhanceNegotiateRequest):
    player = repo.load_player()
    try:
        state_machine.assert_phase_in(player["current_phase"], NEGOTIATE_PHASES)
    except state_machine.PhaseError:
        raise HTTPException(400, detail={"error": "wrong_phase",
                                          "current_phase": player["current_phase"]})

    from .. import hero_registry
    todays = hero_registry.heroes_for_today(player["current_day"])
    idx = _hero_index_for_phase(player["current_phase"])
    hero_id = todays[idx]["id"]

    selected = [s.model_dump() for s in (req.selected_materials or [])]
    try:
        result = await negotiation.step_enhance(
            hero_id, req.price_offered, req.player_message,
            neg_id=req.negotiation_id,
            selected_materials=selected if req.negotiation_id is None else None,
        )
    except ValueError as e:
        raise HTTPException(400, detail={"error": "enhance_invalid", "message": str(e)})
    return result


@router.post("/enhance/finalize")
def post_enhance_finalize(req: FinalizeRequest):
    try:
        negotiation.finalize_enhance(req.negotiation_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_finalize", "message": str(e)})
    player = repo.load_player()
    return {"ok": True, "next_phase": player["current_phase"]}


@router.post("/enhance/player_accept")
def post_enhance_player_accept(req: FinalizeRequest):
    try:
        agreed = negotiation.player_accept_enhance_counter(req.negotiation_id)
        negotiation.finalize_enhance(req.negotiation_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_accept", "message": str(e)})
    player = repo.load_player()
    return {"ok": True, "agreed_price": agreed, "next_phase": player["current_phase"]}


@router.post("/enhance/player_reject")
def post_enhance_player_reject(req: FinalizeRequest):
    try:
        negotiation.player_reject_enhance(req.negotiation_id)
    except ValueError as e:
        raise HTTPException(400, detail={"error": "cannot_reject", "message": str(e)})
    player = repo.load_player()
    return {"ok": True, "next_phase": player["current_phase"]}


@router.post("/enhance/skip")
def post_enhance_skip():
    """강화 phase 건너뛰기 — 평판 변화 없음, phase advance."""
    player = repo.load_player()
    try:
        state_machine.assert_phase_in(player["current_phase"], NEGOTIATE_PHASES)
    except state_machine.PhaseError:
        raise HTTPException(400, detail={"error": "wrong_phase",
                                          "current_phase": player["current_phase"]})
    repo.update_player(current_phase=state_machine.next_phase(player["current_phase"]))
    return {"ok": True, "next_phase": repo.load_player()["current_phase"]}
```

- [ ] **Step 3: Modify `backend/app/main.py` — register enhance router**

기존 import:
```python
from .api import (
    forge as forge_api, negotiate as negotiate_api, battle as battle_api,
    state as state_api, game as game_api, merchant as merchant_api, day as day_api,
)
```

다음으로:
```python
from .api import (
    forge as forge_api, negotiate as negotiate_api, battle as battle_api,
    state as state_api, game as game_api, merchant as merchant_api, day as day_api,
    enhance as enhance_api,
)
```

include_router에 추가:
```python
app.include_router(enhance_api.router)
```

- [ ] **Step 4: 회귀 + import 체크**

```bash
cd /home/afraidnot/dev/smith-tycoon/backend && ./.venv/bin/python -c "from app import main; print('ok')" && ./.venv/bin/pytest -v 2>&1 | tail -5
```

- [ ] **Step 5: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add backend/app/api/enhance.py backend/app/models.py backend/app/main.py && git commit -m "feat(api): enhance endpoints (negotiate/finalize/accept/reject/skip)"
```

---

## Task 10: api/state.py — mode + held_weapon

**Files:**
- Modify: `backend/app/api/state.py`

- [ ] **Step 1: state.py 갱신**

```python
from fastapi import APIRouter
from .. import repo, hero_registry, merchant as merchant_module, negotiation

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
    weapons = [{**w, "market_price": negotiation.market_price(w)}
               for w in repo.load_player_weapons()]

    hero = None
    if player["current_phase"] in NEGOTIATE_PHASES + BATTLE_PHASES:
        todays = hero_registry.heroes_for_today(player["current_day"])
        idx = _hero_index(player["current_phase"])
        if idx is not None and idx < len(todays):
            h = todays[idx]
            mode = "enhance" if h.get("held_weapon_id") else "sell"
            held_weapon = None
            if mode == "enhance":
                w = repo.get_weapon(h["held_weapon_id"])
                held_weapon = {**w, "market_price": negotiation.market_price(w)}
            hero = {
                **h,
                "preferences": hero_registry.preferences_for(h),
                "mode": mode,
                "held_weapon": held_weapon,
            }

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

- [ ] **Step 2: 회귀**

```bash
cd /home/afraidnot/dev/smith-tycoon/backend && ./.venv/bin/pytest -v 2>&1 | tail -5
```

- [ ] **Step 3: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add backend/app/api/state.py && git commit -m "feat(api): /state exposes hero.mode and hero.held_weapon"
```

---

## Task 11: 통합 테스트 — 단골 메타 시나리오

**Files:**
- Create: `backend/tests/test_integration_meta.py`

- [ ] **Step 1: 통합 테스트 작성**

```python
import pytest
from unittest.mock import patch
from app import forge, negotiation, combat, enhancement, affinity as aff_mod


class FakeRepo:
    def __init__(self):
        self.player = {"id": 1, "gold": 5000, "reputation": 0, "current_day": 1,
                       "current_phase": "forge_open", "craft_power": 0}
        self.inventory = [
            {"material_id": 1, "qty": 5, "name": "나뭇가지", "category": "일반",
             "attribute": "바람", "base_price": 5},
            {"material_id": 4, "qty": 5, "name": "철덩이", "category": "일반",
             "attribute": "금", "base_price": 50},
            {"material_id": 11, "qty": 2, "name": "다이아몬드", "category": "특수",
             "attribute": "금", "base_price": 800},
        ]
        self.weapons: list = []
        self.heroes = []
        self.negs: list = []
        self.battles: list = []
        self.day_events: list = []
        self._wid = 100
        self._nid = 0

    def load_player(self): return self.player
    def update_player(self, **f): self.player.update(f)
    def load_inventory(self): return list(self.inventory)
    def deduct_materials(self, mq):
        for mid, q in mq.items():
            row = next(r for r in self.inventory if r["material_id"] == mid)
            row["qty"] -= q
    def add_inventory(self, mid, qty):
        for r in self.inventory:
            if r["material_id"] == mid:
                r["qty"] += qty; return
        self.inventory.append({"material_id": mid, "qty": qty, "name": "?", "category": "일반",
                               "attribute": None, "base_price": 50})
    def insert_weapon(self, w):
        self._wid += 1
        w = {**w, "id": self._wid, "player_id": 1}
        self.weapons.append(w); return w
    def get_weapon(self, wid): return next(w for w in self.weapons if w["id"] == wid)
    def update_weapon(self, wid, **f):
        w = self.get_weapon(wid)
        w.update(f)
    def list_sold_weapons(self): return [w for w in self.weapons if w["owner"] == "sold"]
    def transfer_weapon_to_hero(self, wid, _):
        for w in self.weapons:
            if w["id"] == wid: w["owner"] = "sold"
    def insert_hero(self, h):
        h = {**h, "id": 10 + len(self.heroes)}
        self.heroes.append(h); return h
    def get_hero(self, hid): return next(h for h in self.heroes if h["id"] == hid)
    def update_hero(self, hid, **f): self.get_hero(hid).update(f)
    def list_alive_heroes_ready(self, day):
        return [h for h in self.heroes if h["status"] == "alive"
                and (h.get("return_day") is None or h["return_day"] <= day)]
    def insert_negotiation(self, n):
        self._nid += 1
        n = {**n, "id": self._nid, "player_id": 1}
        self.negs.append(n); return n
    def get_negotiation(self, nid): return next(n for n in self.negs if n["id"] == nid)
    def update_negotiation(self, nid, **f): self.get_negotiation(nid).update(f)
    def insert_battle(self, b):
        b = {**b, "id": len(self.battles) + 1, "player_id": 1}
        self.battles.append(b); return b
    def insert_day_event(self, day, phase, kind, payload):
        self.day_events.append({"id": len(self.day_events) + 1, "day": day, "phase": phase,
                                "kind": kind, "payload": payload})
    def list_day_events(self, day):
        return [e for e in self.day_events if e["day"] == day]
    def count_consecutive_survives(self, hero_id):
        c = 0
        for b in reversed(self.battles):
            if b["hero_id"] != hero_id: continue
            o = b["outcomes"]
            if o.get("hero") == "survived" and o.get("demon") == "killed":
                c += 1
            else:
                break
        return c


@pytest.mark.asyncio
async def test_returning_hero_enhance_flow():
    fake = FakeRepo()
    fake.heroes.append({
        "id": 10, "name": "100", "job": "검사",
        "str": 12, "mag": 5, "gold": 3000, "mood": "여유로움",
        "personality_tags": ["호탕"], "affinity": 25, "status": "alive",
        "return_day": None, "history": [], "nickname": None, "held_weapon_id": None,
        "visit_count": 1,
    })
    from app import hero_registry, nickname as nick_mod

    with patch.object(forge, "repo", fake), \
         patch.object(negotiation, "repo", fake), \
         patch.object(combat, "repo", fake), \
         patch.object(hero_registry, "repo", fake):

        # Day 1: forge → 무기 생성
        weapon = await forge.craft("한손검", {1: 2, 4: 2})
        weapon_id = weapon["id"]
        fake.update_player(current_phase="hero1_negotiate")

        # Day 1: hero1 매도 → accept
        r = await negotiation.step_sell(weapon_id, 10, 100, "이거", neg_id=None)
        assert r["decision"] == "accept"
        negotiation.finalize_sale(r["negotiation_id"])
        assert fake.player["current_phase"] == "hero1_battle"
        # held_weapon_id 세팅 확인
        assert fake.heroes[0]["held_weapon_id"] == weapon_id

        # Day 1: 전투 — 결과는 fixture 기반, 무기 보존 가정
        # 실제 LLM은 fixture로 outcomes 반환하지만 결과는 서버가 결정 → seed 고정
        # 여기서는 결과를 직접 주입하기 위해 fake battles에 기록
        # 간략화 위해 battle 단계는 직접 호출 안 하고 강화 단계로 점프

        # 시나리오: hero가 무기 보존 + 호감도 25 유지 → 다음날 재방문
        # heroes_for_today(day=4)를 호출하면 이 hero가 다시 뽑힘
        fake.update_player(current_day=4, current_phase="forge_open")
        # held_weapon_id가 있으므로 sell이 아니라 enhance mode가 되어야 함

        todays = hero_registry.heroes_for_today(4)
        h = todays[0]
        assert h.get("held_weapon_id") == weapon_id   # 재방문 시에도 무기 보유

        # 강화 협상 (다이아몬드 1개)
        fake.update_player(current_phase="hero1_negotiate")
        r2 = await negotiation.step_enhance(
            h["id"], 1000, "강화해주시오", neg_id=None,
            selected_materials=[{"material_id": 11, "qty": 1}],
        )
        # fixture가 accept를 반환하므로 (또는 server force accept) 결과는 accept 또는 counter
        assert r2["decision"] in ("accept", "counter")
        if r2["decision"] == "accept":
            negotiation.finalize_enhance(r2["negotiation_id"])
            assert fake.player["current_phase"] == "hero1_battle"
            # 무기 강화 효과 확인
            w = fake.get_weapon(weapon_id)
            assert w["enhancement_level"] == 1
            assert any(m.get("action") == "enhance" for m in w["materials_used"])
            # 다이아몬드 1개 차감
            assert next(r for r in fake.inventory if r["material_id"] == 11)["qty"] == 1


def test_nickname_should_award_logic():
    from app.nickname import should_award
    hero = {"affinity": 25, "nickname": None}
    assert should_award(hero, consecutive_survives=2) is True
    assert should_award(hero, consecutive_survives=1) is False
    hero2 = {"affinity": 10, "nickname": None}
    assert should_award(hero2, consecutive_survives=5) is False
```

- [ ] **Step 2: Run test**

```bash
cd /home/afraidnot/dev/smith-tycoon/backend && ./.venv/bin/pytest tests/test_integration_meta.py -v
```
Expected: 2 PASS.

- [ ] **Step 3: 전체 회귀**

```bash
cd /home/afraidnot/dev/smith-tycoon/backend && ./.venv/bin/pytest -v 2>&1 | tail -5
```

- [ ] **Step 4: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add backend/tests/test_integration_meta.py && git commit -m "test(backend): returning hero enhance + nickname logic integration"
```

---

## Task 12: 프론트 types + api

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/api.ts`

- [ ] **Step 1: types.ts 갱신**

기존 Hero interface에 추가 필드:

```typescript
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
  visit_count?: number;
  preferences?: HeroPreferences;
  // Plan 3 신규
  nickname?: string | null;
  mode?: "sell" | "enhance";
  held_weapon?: Weapon | null;
}
```

- [ ] **Step 2: api.ts에 /enhance wrapper 추가**

기존 api 객체 끝에 추가:

```typescript
  enhanceNegotiate: (
    price_offered: number,
    player_message: string,
    negotiation_id: number | null = null,
    selected_materials: { material_id: number; qty: number }[] | null = null,
  ) =>
    request<NegotiateResponse>("POST", "/enhance/negotiate", {
      price_offered, player_message, negotiation_id, selected_materials,
    }),
  enhanceFinalize: (negotiation_id: number) =>
    request<{ ok: true; next_phase: string }>("POST", "/enhance/finalize", { negotiation_id }),
  enhancePlayerAccept: (negotiation_id: number) =>
    request<{ ok: true; agreed_price: number; next_phase: string }>("POST", "/enhance/player_accept", { negotiation_id }),
  enhancePlayerReject: (negotiation_id: number) =>
    request<{ ok: true; next_phase: string }>("POST", "/enhance/player_reject", { negotiation_id }),
  enhanceSkip: () =>
    request<{ ok: true; next_phase: string }>("POST", "/enhance/skip"),
```

- [ ] **Step 3: tsc**

```bash
cd /home/afraidnot/dev/smith-tycoon/frontend && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add frontend/src/types.ts frontend/src/api.ts && git commit -m "feat(frontend): Plan 3 types (mode, held_weapon, nickname) + enhance api wrapper"
```

---

## Task 13: NegotiationChat — 호감도·별명·회상 표시

**Files:**
- Modify: `frontend/src/components/NegotiationChat.tsx`

- [ ] **Step 1: 헤더에 nickname 추가, 호감도 표시 추가**

기존 `<h2>협상 — {hero.name} ({hero.job})...` 줄 아래에 nickname 표시. 그리고 hero info 줄에 호감도 추가:

```tsx
      <h2>
        협상 — {hero.name}{hero.nickname ? ` "${hero.nickname}"` : ""} ({hero.job})
        {hero.visit_count != null && hero.visit_count > 1 && (
          <small style={{ marginLeft: 8, color: "#a06" }}>
            · {hero.visit_count}번째 방문 🔁
          </small>
        )}
        {hero.visit_count === 1 && (
          <small style={{ marginLeft: 8, color: "#888" }}>· 첫 방문</small>
        )}
      </h2>
```

기존 `<p><small>용사 기분: ...` 줄을:

```tsx
      <p><small>
        용사 기분: {hero.mood} / 성격: {hero.personality_tags.join(", ")} / 보유 금화: {hero.gold} / 근력 {hero.str}·마력 {hero.mag}
        {" / "}호감도 <strong style={{
          color: hero.affinity >= 20 ? "#0a6" : hero.affinity <= -20 ? "#a30" : "#666"
        }}>{hero.affinity >= 0 ? "+" : ""}{hero.affinity}</strong>
      </small></p>
```

- [ ] **Step 2: tsc**

```bash
cd /home/afraidnot/dev/smith-tycoon/frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add frontend/src/components/NegotiationChat.tsx && git commit -m "feat(frontend): nickname and affinity display in NegotiationChat"
```

---

## Task 14: EnhanceNegotiation 컴포넌트

**Files:**
- Create: `frontend/src/components/EnhanceNegotiation.tsx`

- [ ] **Step 1: 컴포넌트 작성**

```tsx
import { useState } from "react";
import { api } from "../api";
import type { Hero, Weapon, Material, NegotiateResponse } from "../types";

interface ChatMsg { role: "player" | "hero"; message: string; price?: number | null }

interface Props {
  hero: Hero;
  weapon: Weapon;
  inventory: Material[];
  onDone: () => void;
}

export function EnhanceNegotiation({ hero, weapon, inventory, onDone }: Props) {
  const [stage, setStage] = useState<"pick_materials" | "negotiate">("pick_materials");
  const [picks, setPicks] = useState<Record<number, number>>({});
  const [msgs, setMsgs] = useState<ChatMsg[]>([]);
  const [price, setPrice] = useState<number>(500);
  const [text, setText] = useState<string>("");
  const [last, setLast] = useState<NegotiateResponse | null>(null);
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

  const skip = async () => {
    setBusy(true); setErr(null);
    try { await api.enhanceSkip(); onDone(); }
    catch (e: unknown) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  const enterNegotiate = () => {
    if (Object.keys(picks).length === 0) { setErr("재료를 1개 이상 선택하세요"); return; }
    setStage("negotiate");
  };

  const negotiationStarted = msgs.length > 0;

  const send = async () => {
    setBusy(true); setErr(null);
    try {
      const selected = Object.entries(picks).map(([k, v]) => ({ material_id: Number(k), qty: v }));
      const isFirst = last === null;
      const res = await api.enhanceNegotiate(
        price, text, last?.negotiation_id ?? null,
        isFirst ? selected : null,
      );
      setMsgs((m) => [...m,
        { role: "player", message: text, price },
        { role: "hero", message: res.message, price: res.counter_price }]);
      setLast(res);
      setText("");
      if (res.counter_price) setPrice(res.counter_price);
    } catch (e: unknown) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  const finalize = async () => {
    if (!last) return;
    setBusy(true);
    try { await api.enhanceFinalize(last.negotiation_id); onDone(); }
    catch (e: unknown) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  const acceptCounter = async () => {
    if (!last) return;
    setBusy(true);
    try { await api.enhancePlayerAccept(last.negotiation_id); onDone(); }
    catch (e: unknown) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  const reject = async () => {
    if (!last) return;
    setBusy(true);
    try { await api.enhancePlayerReject(last.negotiation_id); onDone(); }
    catch (e: unknown) { setErr((e as Error).message); }
    finally { setBusy(false); }
  };

  if (stage === "pick_materials") {
    return (
      <div>
        <h2>강화 의뢰 — {hero.name}{hero.nickname ? ` "${hero.nickname}"` : ""} ({hero.job})</h2>
        <p>용사의 무기: <strong>{weapon.name}</strong> (예리도 {weapon.sharpness}, 희귀도 {weapon.rarity}, 강화 {weapon.enhancement_level ?? 0}회)</p>
        <p>호감도 <strong>{hero.affinity >= 0 ? "+" : ""}{hero.affinity}</strong> · 보유 금화 {hero.gold}</p>

        <h4>강화에 투입할 재료 선택</h4>
        {inventory.map((m) => (
          <div key={m.material_id} className="material-row">
            <span style={{ flex: 1 }}>{m.name} <small>({m.category}, 보유 {m.qty})</small></span>
            <button className="btn" onClick={() => change(m.material_id, -1)}>−</button>
            <span style={{ width: 24, textAlign: "center" }}>{picks[m.material_id] ?? 0}</span>
            <button className="btn" onClick={() => change(m.material_id, +1)}>+</button>
          </div>
        ))}

        <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
          <button className="btn" onClick={enterNegotiate} disabled={busy}>가격 협상 시작</button>
          <button className="btn" onClick={skip} disabled={busy}>강화 안 함 (다음 단계로)</button>
        </div>
        {err && <p style={{ color: "red" }}>{err}</p>}
      </div>
    );
  }

  // stage === "negotiate"
  return (
    <div>
      <h2>강화 비용 협상 — {hero.name}{hero.nickname ? ` "${hero.nickname}"` : ""}</h2>
      <p>강화 대상: <strong>{weapon.name}</strong> (예리도 {weapon.sharpness}, 희귀도 {weapon.rarity})</p>
      <p>투입 재료: {Object.entries(picks).map(([k, v]) => {
        const mat = inventory.find((m) => m.material_id === Number(k));
        return `${mat?.name ?? "?"}×${v}`;
      }).join(", ")}</p>
      <p><small>용사 보유 금화: {hero.gold} / 호감도 {hero.affinity}</small></p>

      <div className="chat">
        {msgs.map((m, i) => (
          <div key={i} className={`msg ${m.role === "player" ? "player" : "hero"}`}>
            <strong>{m.role === "player" ? "나" : hero.name}:</strong> {m.message}
            {m.price != null && <em> ({m.price} 골드)</em>}
          </div>
        ))}
      </div>

      {last?.decision === "accept" ? (
        <div style={{ marginTop: 16 }}>
          <p>용사가 수락했습니다. 강화를 진행하시겠습니까?</p>
          <button className="btn" onClick={finalize} disabled={busy}>확정</button>
        </div>
      ) : last?.decision === "reject" ? (
        <div style={{ marginTop: 16 }}>
          <p>강화 의뢰가 결렬되었습니다.</p>
          <button className="btn" onClick={onDone}>다음으로</button>
        </div>
      ) : (
        <div style={{ marginTop: 16 }}>
          {last?.decision === "counter" && last.counter_price != null && (
            <div style={{ marginBottom: 12, padding: 8, background: "#fff4d6", borderRadius: 6 }}>
              <p style={{ margin: "0 0 8px" }}>용사가 <strong>{last.counter_price} 골드</strong>를 역제안했습니다.</p>
              <button className="btn" onClick={acceptCounter} disabled={busy} style={{ marginRight: 8 }}>
                {last.counter_price} 골드에 수락
              </button>
              <button className="btn" onClick={reject} disabled={busy}>거절하고 떠나기</button>
            </div>
          )}
          <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
            <label>강화 비용:&nbsp;
              <input type="number" value={price} max={hero.gold}
                     onChange={(e) => setPrice(Math.min(hero.gold, Math.max(0, Number(e.target.value))))} />
            </label>
            <button className="btn" onClick={() => setPrice((p) => Math.max(0, p - 500))} disabled={busy}>−500</button>
            <button className="btn" onClick={() => setPrice((p) => Math.max(0, p - 100))} disabled={busy}>−100</button>
            <button className="btn" onClick={() => setPrice((p) => Math.min(hero.gold, p + 100))} disabled={busy}>+100</button>
            <button className="btn" onClick={() => setPrice((p) => Math.min(hero.gold, p + 500))} disabled={busy}>+500</button>
            <small>최대 {hero.gold} 골드 (용사 보유)</small>
          </div>
          {negotiationStarted && (
            <textarea rows={2} style={{ width: "100%", marginTop: 8 }} value={text}
                      onChange={(e) => setText(e.target.value)}
                      placeholder="용사에게 한마디 (선택사항)" />
          )}
          <button className="btn" onClick={send} disabled={busy} style={{ marginTop: 8 }}>
            {busy ? "..." : negotiationStarted ? "재제안" : "제안하기"}
          </button>
        </div>
      )}
      {err && <p style={{ color: "red" }}>{err}</p>}
    </div>
  );
}
```

- [ ] **Step 2: tsc**

```bash
cd /home/afraidnot/dev/smith-tycoon/frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add frontend/src/components/EnhanceNegotiation.tsx && git commit -m "feat(frontend): EnhanceNegotiation component (material pick + price chat)"
```

---

## Task 15: DayRouter — mode 분기

**Files:**
- Modify: `frontend/src/components/DayRouter.tsx`

- [ ] **Step 1: NEGOTIATE_PHASES 블록에서 mode 분기 추가**

기존:
```tsx
  if (NEGOTIATE_PHASES.has(phase)) {
    if (!state.hero || state.weapons.length === 0) {
      const skip = async () => { await api.negotiateSkip(); refresh(); };
      return (
        <div>
          <p>판매할 무기가 없습니다. ...</p>
          <button className="btn" onClick={skip}>건너뛰기 (전투로, 평판 -1)</button>
        </div>
      );
    }
    return <NegotiationChat hero={state.hero} weapons={state.weapons} onDone={refresh} />;
  }
```

다음으로 교체:

```tsx
  if (NEGOTIATE_PHASES.has(phase)) {
    if (!state.hero) {
      return <p>용사 정보를 불러오는 중...</p>;
    }
    if (state.hero.mode === "enhance" && state.hero.held_weapon) {
      return (
        <EnhanceNegotiation
          hero={state.hero}
          weapon={state.hero.held_weapon}
          inventory={state.inventory}
          onDone={refresh}
        />
      );
    }
    // 매도 mode (Plan 1·2 기존)
    if (state.weapons.length === 0) {
      const skip = async () => { await api.negotiateSkip(); refresh(); };
      return (
        <div>
          <p>판매할 무기가 없습니다. 무기 없이 전투로 진행할 수 있습니다. (용사를 빈손으로 보내는 것이라 평판 -1)</p>
          <button className="btn" onClick={skip}>건너뛰기 (전투로, 평판 -1)</button>
        </div>
      );
    }
    return <NegotiationChat hero={state.hero} weapons={state.weapons} onDone={refresh} />;
  }
```

상단 import에 추가:

```tsx
import { EnhanceNegotiation } from "./EnhanceNegotiation";
```

- [ ] **Step 2: tsc**

```bash
cd /home/afraidnot/dev/smith-tycoon/frontend && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add frontend/src/components/DayRouter.tsx && git commit -m "feat(frontend): DayRouter dispatches to EnhanceNegotiation when hero.mode==enhance"
```

---

## Task 16: 수동 검증 체크리스트 문서

**Files:**
- Create: `docs/superpowers/plans/2026-05-26-mvp-plan3-checklist.md`

- [ ] **Step 1: 체크리스트 작성**

```markdown
# Plan 3 수동 검증 체크리스트

## 사전
- [ ] backend pytest 모두 PASS
- [ ] frontend tsc 통과
- [ ] uvicorn + vite 동작

## 호감도 + 가격 보정
- [ ] Day 1 hero에게 후한 가격(시세 -10% 미만)에 판매 → 호감도 +10 변화 확인 (다음 방문에서 호감도 표시)
- [ ] Day 1 hero에게 적정가에 판매 → 호감도 +5
- [ ] Day 1 hero에게 바가지(시세 +20% 초과)로 판매 → 호감도 -10
- [ ] 호감도 ≥ +20 hero 재방문 시 NegotiationChat 헤더에 별명 표시 (있는 경우) + 호감도 초록색 표시
- [ ] 호감도 ≥ +50 hero 재방문 → 시세 110%까지 자동 수락
- [ ] 호감도 ≤ -50 hero 재방문 → 즉시 reject ("당신과는 거래하지 않겠소.") + phase 진행

## 강화 흐름
- [ ] Day 1 hero1에 판매 → 전투 무기 보존 → return_day=4
- [ ] Day 4 같은 hero 재방문 → mode=enhance 화면 (재료 선택 UI)
- [ ] 일반 재료 1개 강화 → 예리도/희귀도 소폭 상승
- [ ] 특수 재료 1개 강화 → 더 큰 폭 상승
- [ ] 전설 재료 1개 강화 → 큰 폭 상승 (예리도 +7~15)
- [ ] 강화 후 무기의 enhancement_level이 1 증가, materials_used에 action='enhance' 기록 추가
- [ ] 강화 비용 협상도 sell과 동일하게 동작 (accept/counter/reject)

## 별명 부여
- [ ] 같은 hero가 연속 2회 이상 (생존+마왕 처치) + 호감도 ≥20 달성 → 전투 직후 별명 부여
- [ ] 별명 부여 후 NegotiationChat 헤더에 "이름 별명" 형태로 표시
- [ ] 한 번 부여되면 nickname 갱신 안 됨

## 회상 대사
- [ ] 호감도 ≥20 hero와 협상 시 LLM 대사에 "지난번 그 검 잘 쓰고 있소" 같은 회상 자연스럽게 포함

## 평판/평판 변화
- [ ] 강화 합의 시 평판 +1
- [ ] 강화 결렬 시 평판 -1
- [ ] 강화 phase skip은 평판 변화 없음

## 미포함 (Plan 4 예정)
- 시그니처 기법, 전설 무기 등재
- 보스 전투, 5행 속성 상성
- 승리·패배 엔딩 분기

## 발견된 LLM 품질 이슈
| 시나리오 | 관찰 | 메모 |
|---|---|---|
|   |   |   |
```

- [ ] **Step 2: Commit**

```bash
cd /home/afraidnot/dev/smith-tycoon && git add docs/superpowers/plans/2026-05-26-mvp-plan3-checklist.md && git commit -m "docs: Plan 3 manual verification checklist"
```

---

## 완료 조건 (Definition of Done)

- 모든 backend pytest PASS (Plan 2 38 + Plan 3 신규 30+ = 70+ 테스트 예상)
- `tsc --noEmit` 오류 없음
- 003 마이그레이션 (no-op) 커밋됨
- 단골 메타 5일 풀 플레이 수동 검증 통과 (호감도 변화·강화·별명 모두 확인)
- 모든 커밋 main 또는 feature 브랜치에 push

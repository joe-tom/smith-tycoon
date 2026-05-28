# 인내심 기반 양보폭 U곡선 — 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 4가지 협상(용사 무기 판매 / 상인 자재 구매 / 강화 / 루트 구매)의 라운드별 양보폭을 인내심 값에 따라 1.0×~3.0× U곡선으로 변동시킨다.

**Architecture:** `patience.py`에 순수 함수 `concession_multiplier(patience)` 추가, `negotiation.py`의 4개 cap 계산 지점에 `* mult` 곱셈만 끼워 넣는다. enhance는 현재 cap이 없으므로 신규로 동일 패턴(2라운드 이상에서 작동)을 추가한다.

**Tech Stack:** Python 3.12 + Pytest.

**Spec:** `docs/superpowers/specs/2026-05-28-loot-chitchat-patience-design.md` (말미 "후속" 절)

---

### Task 1: `concession_multiplier` 추가 + 단위 테스트

**Files:**
- Modify: `backend/app/patience.py`
- Modify: `backend/tests/test_patience.py`

- [ ] **Step 1: 실패 테스트 작성**

`backend/tests/test_patience.py` 맨 아래에 추가:

```python
def test_concession_multiplier_midpoint():
    assert patience.concession_multiplier(50) == 1.0


def test_concession_multiplier_quarter_points():
    assert patience.concession_multiplier(25) == 2.0
    assert patience.concession_multiplier(75) == 2.0


def test_concession_multiplier_extremes():
    assert patience.concession_multiplier(0) == 3.0
    assert patience.concession_multiplier(100) == 3.0


def test_concession_multiplier_negative_or_over_clamps():
    # 음수 patience(이론상 exhausted 후)나 100 초과도 안전하게 처리
    assert patience.concession_multiplier(-10) == 3.0
    assert patience.concession_multiplier(150) == 3.0


def test_concession_multiplier_monotonic_from_midpoint():
    # 50에서 멀어질수록 단조 증가
    assert patience.concession_multiplier(60) < patience.concession_multiplier(70)
    assert patience.concession_multiplier(40) < patience.concession_multiplier(30)
```

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_patience.py -v -k concession`
Expected: FAIL (`concession_multiplier` 없음)

- [ ] **Step 3: 구현 추가**

`backend/app/patience.py` 맨 아래에 추가:

```python
def concession_multiplier(patience: int) -> float:
    """양보폭 배수. 50에서 1.0×, 0/100 양 끝에서 3.0× (대칭 U곡선).

    인내심이 가득한 NPC는 기분이 좋아, 거의 탈진한 NPC는 빨리 끝내려고
    후하게 양보한다. 중간 구간(40~60)이 가장 빡빡하다.
    """
    distance = min(abs(patience - 50), 50)
    return 1.0 + distance / 25
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_patience.py -v`
Expected: PASS (기존 + 신규 전부)

- [ ] **Step 5: 커밋**

```bash
git add backend/app/patience.py backend/tests/test_patience.py
git commit -m "feat(patience): concession_multiplier U-curve (1.0×–3.0×)"
```

---

### Task 2: `step_sell` (용사 무기 판매)에 배수 적용

**Files:**
- Modify: `backend/app/negotiation.py:155`
- Modify: `backend/tests/test_negotiation.py`

- [ ] **Step 1: 실패 테스트 작성**

기존 `tests/test_negotiation.py`의 `step_sell` 패턴(`test_step_sell_initializes_patience` 근처)을 참고해 추가. 핵심은: floor 시점에서 patience=50이면 양보폭 5%, patience=100이면 15%여야 한다. `prior_rounds`를 비워 둔 첫 카운터에서 floor를 기준으로 cap이 적용된다.

`tests/test_negotiation.py` 맨 아래에 추가:

```python
@pytest.mark.anyio
async def test_step_sell_concession_widens_with_high_patience(fake_repo, monkeypatch):
    """patience=100이면 1라운드 양보폭이 floor의 15%로 늘어남."""
    from app import negotiation, repo as real_repo
    monkeypatch.setattr(real_repo, "_client", lambda: None)

    pid = fake_repo.insert_player("p_hi_pat")["id"]
    hero = fake_repo.insert_hero(pid, {
        "id": 101, "name": "용사A", "level": 5, "str": 10, "mag": 5,
        "job": "전사", "personality_tags": [], "attribute": "화",
        "gold": 100000, "loot_pending": [], "lore": [],
    })
    weapon = fake_repo.insert_weapon(pid, {
        "id": 200, "name": "검", "type": "검", "attribute": "화",
        "base_price": 1000, "attack": 50, "durability": 10, "sharpness": 5,
        "rarity": 1, "enhancement_level": 0, "materials_used": [],
        "owner": "smith",
    })

    # 선호 무기 가정 → floor = base * 0.8 = 800
    # patience=100, mult=3.0 → max_raise = int(800 * 0.05 * 3.0) = 120
    # cap_this_round = 800 + 120 = 920
    # LLM이 990을 카운터 → 서버가 920으로 잘라야 함

    async def fake_llm(**kw):
        return {"decision": "counter", "counter_price": 990, "message": "990골드 어떻소?"}
    monkeypatch.setattr(negotiation, "_llm_step_sell", fake_llm)

    # _hr.preferences_for가 weapon type을 선호 목록에 포함하도록 monkeypatch
    from app import hero_registry as _hr
    monkeypatch.setattr(_hr, "preferences_for",
                        lambda h: {"types": ["검"], "attributes": ["화"]})

    # patience를 100으로 강제 시작
    monkeypatch.setattr(negotiation, "_pat",
                        type("P", (), {
                            "hero_start": staticmethod(lambda h: 100),
                            "next_after_round": staticmethod(lambda c, conceded: c),
                            "is_exhausted": staticmethod(lambda c: False),
                            "concession_multiplier": staticmethod(
                                lambda p: 1.0 + min(abs(p - 50), 50) / 25),
                        }))

    player = fake_repo.load_player(pid)
    res = await negotiation.step_sell(
        player=player, hero_id=101, weapon_id=200,
        price_offered=500, player_message="500골드 어떻소?",
    )
    assert res["counter_price"] == 920


@pytest.mark.anyio
async def test_step_sell_concession_baseline_at_midpoint_patience(fake_repo, monkeypatch):
    """patience=50이면 기존과 동일한 5% (max_raise=40, cap=840)."""
    from app import negotiation, repo as real_repo
    monkeypatch.setattr(real_repo, "_client", lambda: None)

    pid = fake_repo.insert_player("p_mid_pat")["id"]
    fake_repo.insert_hero(pid, {
        "id": 102, "name": "용사B", "level": 5, "str": 10, "mag": 5,
        "job": "전사", "personality_tags": [], "attribute": "화",
        "gold": 100000, "loot_pending": [], "lore": [],
    })
    fake_repo.insert_weapon(pid, {
        "id": 201, "name": "검", "type": "검", "attribute": "화",
        "base_price": 1000, "attack": 50, "durability": 10, "sharpness": 5,
        "rarity": 1, "enhancement_level": 0, "materials_used": [],
        "owner": "smith",
    })

    async def fake_llm(**kw):
        return {"decision": "counter", "counter_price": 990, "message": "990골드"}
    monkeypatch.setattr(negotiation, "_llm_step_sell", fake_llm)

    from app import hero_registry as _hr
    monkeypatch.setattr(_hr, "preferences_for",
                        lambda h: {"types": ["검"], "attributes": ["화"]})

    monkeypatch.setattr(negotiation, "_pat",
                        type("P", (), {
                            "hero_start": staticmethod(lambda h: 50),
                            "next_after_round": staticmethod(lambda c, conceded: c),
                            "is_exhausted": staticmethod(lambda c: False),
                            "concession_multiplier": staticmethod(
                                lambda p: 1.0 + min(abs(p - 50), 50) / 25),
                        }))

    player = fake_repo.load_player(pid)
    res = await negotiation.step_sell(
        player=player, hero_id=102, weapon_id=201,
        price_offered=500, player_message="500골드",
    )
    assert res["counter_price"] == 840  # 800 + int(800 * 0.05 * 1.0)
```

> **참고:** 기존 테스트가 `fake_repo`, `monkeypatch`, `_llm_step_sell` 패치 패턴을 어떻게 쓰는지 먼저 확인하라. `tests/test_negotiation.py:43` `test_step_sell_initializes_patience` 가 좋은 참고. 위 fixture 사용이 안 맞으면 그 패턴에 맞춰 수정하라 — 핵심은 monkeypatch로 LLM과 patience 시작값을 고정하고 counter_price 결과를 검증하는 것.

- [ ] **Step 2: 테스트 실행 — 실패 확인**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_negotiation.py -v -k "concession"`
Expected: 신규 high_patience 테스트 FAIL, baseline 테스트 PASS (현재 5% 동작이 그대로라서)

- [ ] **Step 3: 구현 수정 — `backend/app/negotiation.py:153-155`**

```python
        # 한 라운드 최대 양보폭: previous 의 5% × 인내심 배수
        previous = max_hero_counter if max_hero_counter is not None else floor
        mult = _pat.concession_multiplier(p_current)
        max_raise = int(previous * 0.05 * mult)
        cap_this_round = previous + max_raise
```

(기존 `max_raise = int(previous * 0.05)` 한 줄을 위 두 줄로 교체)

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_negotiation.py -v -k "step_sell"`
Expected: PASS (신규 2개 + 기존 step_sell 전체)

- [ ] **Step 5: 커밋**

```bash
git add backend/app/negotiation.py backend/tests/test_negotiation.py
git commit -m "feat(negotiation): step_sell concession scaled by patience multiplier"
```

---

### Task 3: `step_buy` (상인 자재 구매)에 배수 적용

**Files:**
- Modify: `backend/app/negotiation.py:408`
- Modify: `backend/tests/test_negotiation.py`

- [ ] **Step 1: 실패 테스트 작성**

기존 `step_buy` 패턴(`test_step_buy_*`)을 참고해 추가. floor = `base * 0.8`. `previous = base = 1000` 가정, patience=100, mult=3.0 → `max_drop = 150`, `min_counter_this_round = 850`. LLM이 700을 카운터 → 850으로 올림.

`tests/test_negotiation.py` 맨 아래에 추가 (기존 step_buy 테스트의 fixture/패치 패턴을 그대로 따라 작성). 검증 핵심: `res["counter_price"] == 850` (patience=100), `res["counter_price"] == 950` (patience=50, 기존 동작 = `1000 - int(1000*0.05) = 950`).

> **구체 코드는 Task 2와 동일한 monkeypatch 패턴**: `_llm_step_buy`를 패치해 fixed counter를 반환, `negotiation._pat`을 패치해 patience 시작값 고정.

- [ ] **Step 2: 실행 — 실패 확인**

- [ ] **Step 3: 구현 수정 — `backend/app/negotiation.py:407-408`**

```python
        previous = min_merch_counter if min_merch_counter is not None else base
        mult = _pat.concession_multiplier(p_current)
        max_drop = int(previous * 0.05 * mult)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_negotiation.py -v -k "step_buy"`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add backend/app/negotiation.py backend/tests/test_negotiation.py
git commit -m "feat(negotiation): step_buy concession scaled by patience multiplier"
```

---

### Task 4: `step_buy_loot` (루트 구매)에 배수 적용

**Files:**
- Modify: `backend/app/negotiation.py:813-814`
- Modify: `backend/tests/test_negotiation.py`

- [ ] **Step 1: 실패 테스트 작성**

기존 `tests/test_step_buy_loot.py`의 패턴을 참고. `previous - int(previous * 0.05 * mult)`. floor = `base * 0.7`은 그대로 — 너무 낮으면 floor가 잡아준다.

검증: `previous = base = 1000`, patience=100, mult=3.0 → drop=150 → counter=850 (floor 700 위). patience=50 → counter=950 (기존).

> **fake_repo 패턴은 `tests/test_step_buy_loot.py` 참조.** 위 두 task와 동일하게 LLM/patience 고정.

- [ ] **Step 2: 실행 — 실패 확인**

- [ ] **Step 3: 구현 수정 — `backend/app/negotiation.py:813-814`**

```python
    previous = min_counter if min_counter is not None else base
    mult = _pat.concession_multiplier(p_current)
    counter = max(int(base * 0.7), previous - int(previous * 0.05 * mult))
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_step_buy_loot.py tests/test_negotiation.py -v -k "loot"`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add backend/app/negotiation.py backend/tests/test_negotiation.py
git commit -m "feat(negotiation): step_buy_loot concession scaled by patience multiplier"
```

---

### Task 5: `step_enhance` (강화)에 신규 cap 추가

**Files:**
- Modify: `backend/app/negotiation.py` (≈line 607-618, enhance counter 처리 블록)
- Modify: `backend/tests/test_negotiation.py`

> **enhance는 현재 5% cap이 없다.** 이 Task에서 신규 추가하면서 동시에 patience 배수를 적용한다. cap은 **2라운드 이상에서만** 작동 (1라운드는 비교할 previous가 없으므로 hero_gold만 상한). 이는 step_sell/buy와 의도적으로 다름 — 강화에는 base_price floor 같은 자연스러운 기준이 없음.

- [ ] **Step 1: 실패 테스트 작성**

검증: 1라운드는 cap 안 걸림 (LLM 자유), 2라운드는 `max_hero_counter` 기준 `5% * mult` 만큼만 양보. patience=50 → 5%, patience=100 → 15%.

예: `max_hero_counter = 1000`, LLM이 700 카운터(=300 양보) 시도, patience=50 → 양보 cap 50 → counter = 950. patience=100 → cap 150 → counter = 850.

> **fake_repo와 `_llm_step_enhance` 패치**: 기존 enhance 테스트(`test_step_enhance_*`)를 참고. 1라운드 negotiation 만들고 max_hero_counter를 강제 setattr한 뒤 2라운드 step.

- [ ] **Step 2: 실행 — 실패 확인**

- [ ] **Step 3: 구현 수정 — `backend/app/negotiation.py` enhance 카운터 블록**

기존 (≈line 609-613):

```python
    if counter is not None:
        counter = max(1, int(counter))
        if max_hero_counter is not None and counter < max_hero_counter:
            counter = max_hero_counter
        counter = min(counter, hero_gold)
```

변경 후:

```python
    if counter is not None:
        counter = max(1, int(counter))
        if max_hero_counter is not None:
            # 단조 비감소 + 인내심 기반 양보 cap (직전가 대비)
            if counter < max_hero_counter:
                counter = max_hero_counter
            mult = _pat.concession_multiplier(p_current)
            max_drop = int(max_hero_counter * 0.05 * mult)
            counter = max(counter, max_hero_counter - max_drop)
        counter = min(counter, hero_gold)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd backend && source .venv/bin/activate && python -m pytest tests/test_negotiation.py -v -k "enhance"`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add backend/app/negotiation.py backend/tests/test_negotiation.py
git commit -m "feat(negotiation): step_enhance gains patience-scaled concession cap"
```

---

### Task 6: 전체 회귀 + UI 수동 확인

**Files:**
- 없음 (검증만)

- [ ] **Step 1: 전체 백엔드 테스트**

Run: `cd backend && source .venv/bin/activate && python -m pytest -q`
Expected: PASS (현재 235개 + 신규 ≈8개)

- [ ] **Step 2: 프론트 타입체크 (회귀 없음 확인)**

Run: `cd frontend && npx tsc --noEmit`
Expected: 출력 없음 (성공)

- [ ] **Step 3: 수동 UI 확인**

Run: `cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000`
Run: `cd frontend && npm run dev`

브라우저에서:
- 호탕 태그 용사(patience 70+ 시작)와 협상 → 1라운드 양보폭이 눈에 띄게 큼
- 깐깐 태그 용사(patience 30 근처)와 협상 → 라운드를 거듭해 patience가 10 근처로 내려갈수록 다시 양보폭이 커짐
- 중간 patience 50 구간에서는 기존처럼 5%만 양보

- [ ] **Step 4: 최종 커밋 없음 — 검증만**

검증 통과하면 작업 종료.

---

## 자기 검토 체크리스트

- [x] 스펙 4가지 적용 지점 모두 Task에 매핑됨 (Task 2/3/4/5)
- [x] `concession_multiplier` 시그니처와 호출이 일관 (`_pat.concession_multiplier(p_current)`)
- [x] enhance가 다른 3개와 다르게 처리되는 이유 명시 (1라운드에 base가 없음)
- [x] 회귀 위험: patience_current가 None일 때 기존 코드는 `or _pat.hero_start(...)` 또는 `or 50`으로 폴백 → multiplier 1.0 또는 그 근방 → 기존 동작 보존

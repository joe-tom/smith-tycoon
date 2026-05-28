import pytest
from app.negotiation import clamp_price, market_price


def test_clamp_price_lower_bound():
    assert clamp_price(10, base=1000) == 100   # 0.1배 하한


def test_clamp_price_upper_bound():
    assert clamp_price(999999, base=1000) == 3000  # 3배 상한


def test_clamp_price_passthrough():
    assert clamp_price(1500, base=1000) == 1500


def test_market_price_uses_materials_and_rarity():
    weapon = {"rarity": 50, "sharpness": 50, "materials_used": [
        {"category": "일반", "qty": 2}, {"category": "특수", "qty": 1}
    ]}
    price = market_price(weapon)
    assert price > 0


def test_clamp_buy_price_lower():
    from app.negotiation import clamp_price
    assert clamp_price(10, base=1000) == 100


def test_market_price_buy_bundle_equivalence():
    from app.merchant import bundle_market_price
    bundle = {"materials": [{"base_price": 100, "qty": 3}], "weapon": None}
    assert bundle_market_price(bundle) == 300


# --- 011: 인내심 통합 ---

import pytest
from app import negotiation as _neg


@pytest.mark.asyncio
async def test_step_sell_initializes_patience(fake_repo, monkeypatch):
    fake_repo.heroes.append({
        "id": 1, "player_id": 1, "name": "H", "job": "검사",
        "str": 5, "mag": 5, "personality_tags": ["깐깐"],
        "affinity": 0, "history": [], "gold": 1000, "lore": [], "loot_pending": [],
    })
    fake_repo.weapons.append({
        "id": 10, "player_id": 1, "owner": "player", "name": "검", "type": "검",
        "rarity": 0, "sharpness": 30, "materials_used": [{"category": "일반"}],
        "attribute": "화",
    })
    fake_repo.players[1] = {"id": 1, "current_day": 1, "current_phase": "visitor",
                             "reputation": 0}
    monkeypatch.setattr(_neg, "repo", fake_repo)

    res = await _neg.step_sell(
        fake_repo.players[1], weapon_id=10, hero_id=1, price_offered=100,
        player_message="첫 제안", neg_id=None,
    )
    neg = fake_repo.get_negotiation(res["negotiation_id"])
    # 깐깐 → start 30, 첫 라운드는 감소 X
    assert neg["patience_start"] == 30
    assert neg["patience_current"] == 30
    assert res["patience_current"] == 30
    assert res["patience_start"] == 30


@pytest.mark.asyncio
async def test_step_sell_patience_decrements_subsequent_round(fake_repo, monkeypatch):
    fake_repo.heroes.append({
        "id": 1, "player_id": 1, "name": "H", "job": "검사",
        "str": 5, "mag": 5, "personality_tags": ["호탕"],   # start 70
        "affinity": 0, "history": [], "gold": 1000, "lore": [], "loot_pending": [],
    })
    fake_repo.weapons.append({
        "id": 10, "player_id": 1, "owner": "player", "name": "검", "type": "검",
        "rarity": 0, "sharpness": 30, "materials_used": [{"category": "일반"}],
        "attribute": "화",
    })
    fake_repo.players[1] = {"id": 1, "current_day": 1, "current_phase": "visitor",
                             "reputation": 0}
    monkeypatch.setattr(_neg, "repo", fake_repo)

    res1 = await _neg.step_sell(fake_repo.players[1], 10, 1, 100, "1", None)
    res2 = await _neg.step_sell(fake_repo.players[1], 10, 1, 100, "2", res1["negotiation_id"])
    # 두 번째 라운드는 -10 (양보 없음)
    assert res2["patience_current"] == 60


@pytest.mark.asyncio
async def test_step_sell_auto_reject_when_patience_exhausted(fake_repo, monkeypatch):
    fake_repo.heroes.append({
        "id": 1, "player_id": 1, "name": "H", "job": "검사",
        "str": 5, "mag": 5, "personality_tags": ["깐깐", "소심"],  # start 20
        "affinity": 0, "history": [], "gold": 1000, "lore": [], "loot_pending": [],
    })
    fake_repo.weapons.append({
        "id": 10, "player_id": 1, "owner": "player", "name": "검", "type": "검",
        "rarity": 0, "sharpness": 30, "materials_used": [{"category": "일반"}],
        "attribute": "화",
    })
    fake_repo.players[1] = {"id": 1, "current_day": 1, "current_phase": "visitor",
                             "reputation": 5}
    monkeypatch.setattr(_neg, "repo", fake_repo)

    # 20 → (skip 1라) → 10 → 0 → exhausted
    r1 = await _neg.step_sell(fake_repo.players[1], 10, 1, 100, "1", None)
    r2 = await _neg.step_sell(fake_repo.players[1], 10, 1, 100, "2", r1["negotiation_id"])
    r3 = await _neg.step_sell(fake_repo.players[1], 10, 1, 100, "3", r1["negotiation_id"])
    assert r3["decision"] == "reject"
    neg = fake_repo.get_negotiation(r1["negotiation_id"])
    assert neg["outcome"] == "rejected"
    assert fake_repo.players[1]["reputation"] == 4
    h = fake_repo.get_hero(1)
    assert h["affinity"] == -1


# --- 인내심 양보폭 배수 ---

@pytest.mark.asyncio
async def test_step_sell_concession_cap_baseline_patience(fake_repo, monkeypatch):
    """patience=50(기본) → mult=1.0 → 5%만 양보.

    base = market_price(weapon):
      mat_value = 50 (일반 qty=1), rarity_mult=1.0, sharp_mult=1.15
      base = int(50 * 1.0 * 1.15) = 57
    검사 선호: ["검", "둔기"], weapon type "검" → fits → floor = int(57 * 0.8) = 45
    previous = floor = 45 (첫 라운드, 이전 hero counter 없음)
    mult = concession_multiplier(50) = 1.0
    max_raise = int(45 * 0.05 * 1.0) = int(2.25) = 2
    cap_this_round = 45 + 2 = 47
    LLM counter=9999 → clamp_price(9999, 57)=171 → floor check >=45 OK
    → cap: 171 > 47 → counter = 47
    player offers 200 > 47 → counter < safe_price → decision stays counter
    """
    from unittest.mock import AsyncMock

    fake_repo.heroes.append({
        "id": 1, "player_id": 1, "name": "H", "job": "검사",
        "str": 5, "mag": 5, "personality_tags": [],  # patience_start = 50
        "affinity": 0, "history": [], "gold": 1000, "lore": [], "loot_pending": [],
    })
    fake_repo.weapons.append({
        "id": 10, "player_id": 1, "owner": "player", "name": "검", "type": "검",
        "rarity": 0, "sharpness": 30,
        "materials_used": [{"category": "일반"}],
        "attribute": None,
    })
    fake_repo.players[1] = {
        "id": 1, "current_day": 1, "current_phase": "visitor", "reputation": 0,
    }
    monkeypatch.setattr(_neg, "repo", fake_repo)
    monkeypatch.setattr(_neg, "complete_json", AsyncMock(
        return_value={"decision": "counter", "counter_price": 9999, "message": "비싸오."}
    ))

    # player offers 200 (> cap=47) → hero counters at cap, stays counter
    res = await _neg.step_sell(
        fake_repo.players[1], weapon_id=10, hero_id=1,
        price_offered=200, player_message="살게요", neg_id=None,
    )
    assert res["decision"] == "counter"
    # base=57, floor=45, previous=45, mult=1.0, max_raise=int(2.25)=2, cap=47
    assert res["counter_price"] == 47


@pytest.mark.asyncio
async def test_step_sell_concession_cap_high_patience_triple_raise(fake_repo, monkeypatch):
    """patience=100 → mult=3.0 → 15%까지 양보.

    Pre-seeded negotiation with patience_current=100, rounds=[] (첫 라운드와 동일 조건으로
    patience 감소 없음). LLM mocked to return high counter.

    base=57, floor=45, previous=45 (no prior hero counter)
    mult = concession_multiplier(100) = 1.0 + 50/25 = 3.0
    max_raise = int(45 * 0.05 * 3.0) = int(6.75) = 6
    cap_this_round = 45 + 6 = 51
    player offers 200 > 51 → counter < safe_price → decision stays counter, counter_price = 51
    """
    from unittest.mock import AsyncMock

    fake_repo.heroes.append({
        "id": 2, "player_id": 1, "name": "G", "job": "검사",
        "str": 5, "mag": 5, "personality_tags": [],
        "affinity": 0, "history": [], "gold": 1000, "lore": [], "loot_pending": [],
    })
    fake_repo.weapons.append({
        "id": 20, "player_id": 1, "owner": "player", "name": "장검", "type": "검",
        "rarity": 0, "sharpness": 30,
        "materials_used": [{"category": "일반"}],
        "attribute": None,
    })
    fake_repo.players[1] = {
        "id": 1, "current_day": 1, "current_phase": "visitor", "reputation": 0,
    }
    monkeypatch.setattr(_neg, "repo", fake_repo)
    monkeypatch.setattr(_neg, "complete_json", AsyncMock(
        return_value={"decision": "counter", "counter_price": 9999, "message": "비싸오."}
    ))

    # Pre-seed negotiation with patience_current=100 and empty rounds
    # (empty rounds → patience decrement skipped, stays at 100)
    fake_repo._neg_seq += 1
    pre_neg_id = fake_repo._neg_seq
    fake_repo.negotiations.append({
        "id": pre_neg_id, "player_id": 1,
        "day": 1, "phase": "visitor",
        "kind": "sell", "counterparty_id": 2, "weapon_id": 20,
        "rounds": [], "outcome": "open",
        "patience_start": 100, "patience_current": 100,
    })

    # player offers 200 (> cap=51) → hero counters at cap, stays counter
    res = await _neg.step_sell(
        fake_repo.players[1], weapon_id=20, hero_id=2,
        price_offered=200, player_message="살게요", neg_id=pre_neg_id,
    )
    assert res["decision"] == "counter"
    # base=57, floor=45, previous=45, mult=3.0, max_raise=int(6.75)=6, cap=51
    assert res["counter_price"] == 51


# --- step_buy 인내심 양보폭 배수 ---

@pytest.mark.asyncio
async def test_step_buy_concession_cap_baseline_patience(fake_repo, monkeypatch):
    """patience=50(기본) → mult=1.0 → 5%만 양보(인하).

    bundle: materials=[{asking_price=100, qty=1, base_price=100, material_id=1}], weapon=None
    base = bundle_market_price(bundle) = 100
    previous = base = 100 (이전 상인 카운터 없음)
    mult = concession_multiplier(50) = 1.0
    max_drop = int(100 * 0.05 * 1.0) = 5
    min_counter_this_round = 100 - 5 = 95
    LLM counter=1 → clamp_price(1, 100)=10 → 10 < 95 → counter = 95
    player offers 1 (< 95) → stays counter
    """
    from unittest.mock import AsyncMock

    fake_repo.players[1] = {
        "id": 1, "current_day": 1, "current_phase": "merchant", "reputation": 0,
        "gold": 1000,
    }
    monkeypatch.setattr(_neg, "repo", fake_repo)
    monkeypatch.setattr(_neg, "complete_json", AsyncMock(
        return_value={"decision": "counter", "counter_price": 1, "message": "이거이거."}
    ))

    bundle = {
        "materials": [{"material_id": 1, "base_price": 100, "qty": 1, "asking_price": 100}],
        "weapon": None,
    }
    fake_repo._neg_seq += 1
    pre_neg_id = fake_repo._neg_seq
    fake_repo.negotiations.append({
        "id": pre_neg_id, "player_id": 1,
        "day": 1, "phase": "merchant",
        "kind": "buy", "counterparty_id": 10, "weapon_id": None,
        "materials": bundle, "rounds": [], "outcome": "open",
        "patience_start": 50, "patience_current": 50,
    })

    # _client_or_repo_get_merchant은 neg_id 분기 전 무조건 호출됨 — stub 필요
    monkeypatch.setattr(
        _neg, "_client_or_repo_get_merchant",
        lambda merchant_id: {"id": merchant_id, "materials": [], "weapon": None},
    )

    # player offers 1 (well below any cap) — merchant counters at cap=95
    res = await _neg.step_buy(
        fake_repo.players[1], merchant_id=10, price_offered=1,
        player_message="싸게 주세요", neg_id=pre_neg_id,
    )
    assert res["decision"] == "counter"
    # base=100, previous=100, mult=1.0, max_drop=5, min_counter=95
    assert res["counter_price"] == 95


@pytest.mark.asyncio
async def test_step_buy_concession_cap_high_patience_triple_drop(fake_repo, monkeypatch):
    """patience=100 → mult=3.0 → 15%까지 양보(인하).

    bundle: materials=[{asking_price=100, qty=1, base_price=100, material_id=1}], weapon=None
    base = 100
    previous = base = 100 (이전 상인 카운터 없음)
    mult = concession_multiplier(100) = 1.0 + 50/25 = 3.0
    max_drop = int(100 * 0.05 * 3.0) = 15
    min_counter_this_round = 100 - 15 = 85
    LLM counter=1 → clamp_price(1, 100)=10 → 10 < 85 → counter = 85
    player offers 1 (< 85) → stays counter
    """
    from unittest.mock import AsyncMock

    fake_repo.players[1] = {
        "id": 1, "current_day": 1, "current_phase": "merchant", "reputation": 0,
        "gold": 1000,
    }
    monkeypatch.setattr(_neg, "repo", fake_repo)
    monkeypatch.setattr(_neg, "complete_json", AsyncMock(
        return_value={"decision": "counter", "counter_price": 1, "message": "이거이거."}
    ))

    bundle = {
        "materials": [{"material_id": 1, "base_price": 100, "qty": 1, "asking_price": 100}],
        "weapon": None,
    }
    fake_repo._neg_seq += 1
    pre_neg_id = fake_repo._neg_seq
    fake_repo.negotiations.append({
        "id": pre_neg_id, "player_id": 1,
        "day": 1, "phase": "merchant",
        "kind": "buy", "counterparty_id": 10, "weapon_id": None,
        "materials": bundle, "rounds": [], "outcome": "open",
        "patience_start": 100, "patience_current": 100,
    })

    # _client_or_repo_get_merchant은 neg_id 분기 전 무조건 호출됨 — stub 필요
    monkeypatch.setattr(
        _neg, "_client_or_repo_get_merchant",
        lambda merchant_id: {"id": merchant_id, "materials": [], "weapon": None},
    )

    # player offers 1 (well below any cap) — merchant counters at cap=85
    res = await _neg.step_buy(
        fake_repo.players[1], merchant_id=10, price_offered=1,
        player_message="많이 깎아주세요", neg_id=pre_neg_id,
    )
    assert res["decision"] == "counter"
    # base=100, previous=100, mult=3.0, max_drop=15, min_counter=85
    assert res["counter_price"] == 85


# --- step_enhance 인내심 양보폭 배수 ---

def _enhance_pre_neg(fake_repo, hero_id: int, weapon_id: int,
                     max_hero_counter: int, patience_current: int,
                     prior_player_price: int = 999) -> int:
    """Round 2 시나리오용: 이전 라운드에 hero counter 기록이 있는 협상을 세팅.

    prior_player_price: 직전 라운드 플레이어 제시가. 양보 여부(conceded) 계산에 영향.
      - conceded = (prior_player_price < 이번_safe_price)
      - 양보 없으면 patience -10, 있으면 -5.
    patience_current: 이번 라운드 시작 전 값. 감소 후 값이 테스트 기대치가 됨.
    """
    fake_repo._neg_seq += 1
    neg_id = fake_repo._neg_seq
    fake_repo.negotiations.append({
        "id": neg_id, "player_id": 1,
        "day": 1, "phase": "enhance",
        "kind": "enhance", "counterparty_id": hero_id, "weapon_id": weapon_id,
        "materials": {
            "selected": [{"material_id": 1, "name": "철", "category": "일반",
                          "attribute": None, "qty": 1}],
            "base_estimate": 100,
        },
        "rounds": [
            {"role": "player", "message": "부탁합니다", "price": prior_player_price},
            {"role": "hero", "message": "좀 더 주시오.", "price": max_hero_counter},
        ],
        "outcome": "open",
        "patience_start": patience_current,
        "patience_current": patience_current,
    })
    return neg_id


@pytest.mark.asyncio
async def test_step_enhance_concession_baseline_patience(fake_repo, monkeypatch):
    """patience=50(기본) → mult=1.0 → 5%까지만 카운터 상승.

    max_hero_counter = 200 (직전 라운드 hero 제시가)
    patience 추적:
      prior_player_price=999, safe_price=500 → conceded=(999<500)=False → p -10
      patience_current seeded at 60 → after decrement: p_current=50
    mult = concession_multiplier(50) = 1.0
    max_raise = int(200 * 0.05 * 1.0) = 10
    cap = 200 + 10 = 210
    LLM counter=9999 → min(9999, 210) = 210 (hero_gold=1000 > 210)
    player offers 500 > 210 → stays counter, counter_price = 210
    """
    from unittest.mock import AsyncMock

    fake_repo.heroes.append({
        "id": 1, "player_id": 1, "name": "H", "job": "검사",
        "str": 5, "mag": 5, "personality_tags": [],  # patience_start = 50
        "affinity": 0, "history": [], "gold": 1000, "lore": [], "loot_pending": [],
        "held_weapon_id": 10,
    })
    fake_repo.weapons.append({
        "id": 10, "player_id": 1, "owner": "hero", "name": "검", "type": "검",
        "rarity": 0, "sharpness": 30,
        "materials_used": [{"category": "일반"}],
        "attribute": None,
    })
    fake_repo.players[1] = {
        "id": 1, "current_day": 1, "current_phase": "enhance", "reputation": 0,
    }
    monkeypatch.setattr(_neg, "repo", fake_repo)
    monkeypatch.setattr(_neg, "complete_json", AsyncMock(
        return_value={"decision": "counter", "counter_price": 9999, "message": "더 주시오."}
    ))

    # patience_current=60, prior_player_price=999, safe_price=500
    # conceded=(999<500)=False → p -10 → p_current=50 → mult=1.0
    neg_id = _enhance_pre_neg(fake_repo, hero_id=1, weapon_id=10,
                               max_hero_counter=200, patience_current=60,
                               prior_player_price=999)

    # player offers 500 (> cap=210) → hero counters at 210
    res = await _neg.step_enhance(
        fake_repo.players[1], hero_id=1, price_offered=500,
        player_message="500에 해주세요", neg_id=neg_id,
    )
    assert res["decision"] == "counter"
    # p_current=50, mult=1.0, max_raise=int(200*0.05*1.0)=10, cap=210
    assert res["counter_price"] == 210


@pytest.mark.asyncio
async def test_step_enhance_concession_high_patience_triple_raise(fake_repo, monkeypatch):
    """patience=100 → mult=3.0 → 15%까지 카운터 상승.

    max_hero_counter = 200
    patience 추적:
      prior_player_price=1, safe_price=500 → conceded=(1<500)=True → p -5
      patience_current seeded at 105 → after decrement: p_current=100
    mult = concession_multiplier(100) = 1.0 + 50/25 = 3.0
    max_raise = int(200 * 0.05 * 3.0) = 30
    cap = 200 + 30 = 230
    LLM counter=9999 → min with hero_gold=1000=1000, then cap → min(1000, 230) = 230
    player offers 500 > 230 → stays counter, counter_price = 230
    """
    from unittest.mock import AsyncMock

    fake_repo.heroes.append({
        "id": 2, "player_id": 1, "name": "G", "job": "검사",
        "str": 5, "mag": 5, "personality_tags": [],
        "affinity": 0, "history": [], "gold": 1000, "lore": [], "loot_pending": [],
        "held_weapon_id": 20,
    })
    fake_repo.weapons.append({
        "id": 20, "player_id": 1, "owner": "hero", "name": "장검", "type": "검",
        "rarity": 0, "sharpness": 30,
        "materials_used": [{"category": "일반"}],
        "attribute": None,
    })
    fake_repo.players[1] = {
        "id": 1, "current_day": 1, "current_phase": "enhance", "reputation": 0,
    }
    monkeypatch.setattr(_neg, "repo", fake_repo)
    monkeypatch.setattr(_neg, "complete_json", AsyncMock(
        return_value={"decision": "counter", "counter_price": 9999, "message": "더 주시오."}
    ))

    # patience_current=105, prior_player_price=1, safe_price=500
    # conceded=(1<500)=True → p -5 → p_current=100 → mult=3.0
    neg_id = _enhance_pre_neg(fake_repo, hero_id=2, weapon_id=20,
                               max_hero_counter=200, patience_current=105,
                               prior_player_price=1)

    # player offers 500 (> cap=230) → hero counters at 230
    res = await _neg.step_enhance(
        fake_repo.players[1], hero_id=2, price_offered=500,
        player_message="500에 해주세요", neg_id=neg_id,
    )
    assert res["decision"] == "counter"
    # p_current=100, mult=3.0, max_raise=int(200*0.05*3.0)=30, cap=230
    assert res["counter_price"] == 230


@pytest.mark.asyncio
async def test_step_enhance_concession_no_cap_round_one(fake_repo, monkeypatch):
    """첫 라운드 (no prior hero counter) → cap 미작동, LLM counter 그대로 통과.

    max_hero_counter = None → concession cap block skipped entirely.
    LLM counter=150, player offers 500 > 150 → decision=counter, counter_price=150.
    """
    from unittest.mock import AsyncMock

    fake_repo.heroes.append({
        "id": 3, "player_id": 1, "name": "K", "job": "검사",
        "str": 5, "mag": 5, "personality_tags": [],
        "affinity": 0, "history": [], "gold": 1000, "lore": [], "loot_pending": [],
        "held_weapon_id": 30,
    })
    fake_repo.weapons.append({
        "id": 30, "player_id": 1, "owner": "hero", "name": "단검", "type": "검",
        "rarity": 0, "sharpness": 30,
        "materials_used": [{"category": "일반"}],
        "attribute": None,
    })
    fake_repo.players[1] = {
        "id": 1, "current_day": 1, "current_phase": "enhance", "reputation": 0,
    }
    monkeypatch.setattr(_neg, "repo", fake_repo)
    monkeypatch.setattr(_neg, "complete_json", AsyncMock(
        return_value={"decision": "counter", "counter_price": 150, "message": "150 주시오."}
    ))

    # Pre-seed negotiation with no prior rounds (round 1 scenario)
    fake_repo._neg_seq += 1
    neg_id = fake_repo._neg_seq
    fake_repo.negotiations.append({
        "id": neg_id, "player_id": 1,
        "day": 1, "phase": "enhance",
        "kind": "enhance", "counterparty_id": 3, "weapon_id": 30,
        "materials": {
            "selected": [{"material_id": 1, "name": "철", "category": "일반",
                          "attribute": None, "qty": 1}],
            "base_estimate": 100,
        },
        "rounds": [],  # 첫 라운드 — prior hero counters 없음
        "outcome": "open",
        "patience_start": 50, "patience_current": 50,
    })

    # player offers 500 → LLM counter 150 passes through cap (no max_hero_counter)
    res = await _neg.step_enhance(
        fake_repo.players[1], hero_id=3, price_offered=500,
        player_message="500에 해주세요", neg_id=neg_id,
    )
    assert res["decision"] == "counter"
    assert res["counter_price"] == 150

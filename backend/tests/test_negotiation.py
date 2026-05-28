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

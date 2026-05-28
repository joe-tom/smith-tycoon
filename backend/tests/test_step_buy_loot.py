import pytest
from app import negotiation as _neg


def _hero(**kw):
    base = {
        "id": 1, "player_id": 1, "name": "H", "personality_tags": [],
        "affinity": 0, "history": [], "loot_pending": [], "lore": [],
    }
    base.update(kw)
    return base


@pytest.mark.asyncio
async def test_buy_loot_auto_accept_at_asking(fake_repo, monkeypatch):
    fake_repo.heroes.append(_hero(loot_pending=[
        {"material_id": 1, "qty": 2}, {"material_id": 2, "qty": 1},
    ]))
    fake_repo.materials = [
        {"id": 1, "category": "일반", "base_price": 50, "name": "철"},
        {"id": 2, "category": "일반", "base_price": 100, "name": "강철"},
    ]
    fake_repo.players[1] = {"id": 1, "current_day": 1, "gold": 10000,
                             "current_phase": "visitor", "reputation": 0}
    monkeypatch.setattr(_neg, "repo", fake_repo)

    # base 200, mult 1.2 → asking 240. 정확히 asking → accept
    res = await _neg.step_buy_loot(fake_repo.players[1], 1, 240, "다 살게", None)
    assert res["decision"] == "accept"


@pytest.mark.asyncio
async def test_buy_loot_high_affinity_lowers_asking(fake_repo, monkeypatch):
    fake_repo.heroes.append(_hero(affinity=100,
        loot_pending=[{"material_id": 1, "qty": 2}]))
    fake_repo.materials = [{"id": 1, "category": "일반", "base_price": 50, "name": "철"}]
    fake_repo.players[1] = {"id": 1, "current_day": 1, "gold": 10000,
                             "current_phase": "visitor", "reputation": 0}
    monkeypatch.setattr(_neg, "repo", fake_repo)

    # base 100, mult 0.7 → asking 70
    res = await _neg.step_buy_loot(fake_repo.players[1], 1, 70, "고맙다", None)
    assert res["decision"] == "accept"


@pytest.mark.asyncio
async def test_buy_loot_low_offer_returns_counter(fake_repo, monkeypatch):
    fake_repo.heroes.append(_hero(loot_pending=[{"material_id": 1, "qty": 2}]))
    fake_repo.materials = [{"id": 1, "category": "일반", "base_price": 50, "name": "철"}]
    fake_repo.players[1] = {"id": 1, "current_day": 1, "gold": 10000,
                             "current_phase": "visitor", "reputation": 0}
    monkeypatch.setattr(_neg, "repo", fake_repo)

    # asking 120 (100*1.2). 10 제시 → counter
    res = await _neg.step_buy_loot(fake_repo.players[1], 1, 10, "싸게 줘", None)
    assert res["decision"] == "counter"
    assert res["counter_price"] is not None


def test_finalize_buy_loot_transfers_and_bumps_affinity(fake_repo, monkeypatch):
    fake_repo.heroes.append(_hero(affinity=10,
        loot_pending=[{"material_id": 1, "qty": 2}]))
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
    monkeypatch.setattr(_neg, "repo", fake_repo)

    _neg.finalize_buy_loot(fake_repo.players[1], 1)
    assert fake_repo.players[1]["gold"] == 900
    inv = fake_repo.inventory[1]
    assert any(r["material_id"] == 1 and r["qty"] == 2 for r in inv)
    h = fake_repo.get_hero(1)
    assert h["affinity"] == 15
    assert h["loot_pending"] == []


def test_finalize_buy_loot_idempotent(fake_repo, monkeypatch):
    fake_repo.heroes.append(_hero(affinity=10,
        loot_pending=[{"material_id": 1, "qty": 2}]))
    fake_repo.materials = [{"id": 1, "category": "일반", "base_price": 50, "name": "철"}]
    fake_repo.players[1] = {"id": 1, "current_day": 1, "gold": 1000,
                             "current_phase": "visitor", "reputation": 0}
    fake_repo.negotiations.append({
        "id": 1, "player_id": 1, "kind": "buy_loot", "counterparty_id": 1,
        "outcome": "accepted", "agreed_price": 100,
        "materials": {"items": [{"material_id": 1, "qty": 2}]},
        "rounds": [], "finalized": True,
    })
    monkeypatch.setattr(_neg, "repo", fake_repo)
    assert _neg.finalize_buy_loot(fake_repo.players[1], 1) is False
    # 골드 변화 없음
    assert fake_repo.players[1]["gold"] == 1000


# --- step_buy_loot 인내심 양보폭 배수 ---

@pytest.mark.asyncio
async def test_step_buy_loot_concession_baseline_patience(fake_repo, monkeypatch):
    """patience=50(기본) → mult=1.0 → 5%만 양보(인하).

    loot: [{material_id=1, base_price=100, qty=1}], affinity=0
    total=100, multiplier=max(0.5, 1.2-0/200)=1.2 → asking=120
    previous = base = 120 (이전 영웅 카운터 없음)
    mult = concession_multiplier(50) = 1.0
    max_drop = int(120 * 0.05 * 1.0) = 6
    counter = max(int(120*0.7)=84, 120-6=114) = 114
    player offers 1 (< 114) → counter 반환
    """
    fake_repo.heroes.append(_hero(loot_pending=[{"material_id": 1, "qty": 1}]))
    fake_repo.materials = [{"id": 1, "category": "일반", "base_price": 100, "name": "철"}]
    fake_repo.players[1] = {"id": 1, "current_day": 1, "gold": 10000,
                             "current_phase": "visitor", "reputation": 0}
    monkeypatch.setattr(_neg, "repo", fake_repo)

    # 첫 라운드(neg_id=None) — hero에 personality_tags=[] → patience_start=50
    res = await _neg.step_buy_loot(fake_repo.players[1], 1, 1, "싸게 줘", None)
    assert res["decision"] == "counter"
    # base=120, previous=120, mult=1.0, drop=6, counter=114
    assert res["counter_price"] == 114


@pytest.mark.asyncio
async def test_step_buy_loot_concession_high_patience_triple_drop(fake_repo, monkeypatch):
    """patience=100 → mult=3.0 → 15%까지 양보(인하).

    loot: [{material_id=1, base_price=100, qty=1}], affinity=0
    asking=120, previous=120
    mult = concession_multiplier(100) = 1.0 + 50/25 = 3.0
    max_drop = int(120 * 0.05 * 3.0) = 18
    counter = max(int(120*0.7)=84, 120-18=102) = 102
    player offers 1 (< 102) → counter 반환
    """
    fake_repo.heroes.append(_hero(loot_pending=[{"material_id": 1, "qty": 1}]))
    fake_repo.materials = [{"id": 1, "category": "일반", "base_price": 100, "name": "철"}]
    fake_repo.players[1] = {"id": 1, "current_day": 1, "gold": 10000,
                             "current_phase": "visitor", "reputation": 0}
    monkeypatch.setattr(_neg, "repo", fake_repo)

    # pre-seed a negotiation with patience_current=100
    fake_repo._neg_seq += 1
    pre_neg_id = fake_repo._neg_seq
    fake_repo.negotiations.append({
        "id": pre_neg_id, "player_id": 1,
        "day": 1, "phase": "visitor",
        "kind": "buy_loot", "counterparty_id": 1, "weapon_id": None,
        "materials": {"items": [{"material_id": 1, "qty": 1}], "asking": 120},
        "rounds": [], "outcome": "open",
        "patience_start": 100, "patience_current": 100,
    })

    res = await _neg.step_buy_loot(fake_repo.players[1], 1, 1, "싸게 줘", pre_neg_id)
    assert res["decision"] == "counter"
    # base=120, previous=120, mult=3.0, drop=18, counter=102
    assert res["counter_price"] == 102

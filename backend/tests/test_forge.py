import pytest
from app.forge import roll_weapon_stats, effort_cost, effort_penalty_pct


def test_roll_weapon_stats_deterministic_with_seed():
    stats1 = roll_weapon_stats(["일반", "일반"], seed=42)
    stats2 = roll_weapon_stats(["일반", "일반"], seed=42)
    assert stats1 == stats2


def test_legendary_material_boosts_rarity():
    common = roll_weapon_stats(["일반", "일반"], seed=1)
    legendary = roll_weapon_stats(["전설", "전설"], seed=1)
    assert legendary["rarity"] > common["rarity"]


def test_stats_clamped_0_100():
    for s in range(20):
        stats = roll_weapon_stats(["전설", "전설", "전설", "전설"], seed=s)
        assert 0 <= stats["rarity"] <= 100
        assert 0 <= stats["sharpness"] <= 100


# --- 노력(effort) 시스템 ---

def test_effort_cost_common_one_each():
    used = [{"category": "일반", "qty": 2}, {"category": "이상한", "qty": 1}]
    assert effort_cost(used) == 15  # 6*2 + 3*1


def test_effort_cost_special_weighted():
    used = [{"category": "특수", "qty": 2}]
    assert effort_cost(used) == 20  # 10*2


def test_effort_cost_legendary_weighted():
    used = [{"category": "전설", "qty": 1}, {"category": "일반", "qty": 1}]
    assert effort_cost(used) == 26  # 20 + 6


def test_effort_penalty_zero_when_no_shortage():
    assert effort_penalty_pct(0) == 0
    assert effort_penalty_pct(-5) == 0


def test_effort_penalty_30_when_shortage_1_to_10():
    assert effort_penalty_pct(1) == 30
    assert effort_penalty_pct(10) == 30


def test_effort_penalty_70_when_shortage_over_10():
    assert effort_penalty_pct(11) == 70
    assert effort_penalty_pct(100) == 70

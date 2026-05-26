import pytest
from app.forge import roll_weapon_stats


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

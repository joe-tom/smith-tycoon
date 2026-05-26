import pytest
from app.combat import boss_spawn_chance


@pytest.mark.parametrize("day,expected", [
    (1, 0.0), (39, 0.0),
    (40, 0.05), (59, 0.05),
    (60, 0.10), (79, 0.10),
    (80, 0.25), (89, 0.25),
    (90, 1.0), (99, 1.0),
    (100, 1.0), (150, 1.0),
])
def test_boss_spawn_chance(day, expected):
    assert boss_spawn_chance(day) == pytest.approx(expected)


from app.combat import roll_demon


def test_roll_demon_day_under_40_never_boss():
    for seed in range(50):
        d = roll_demon(day=20, defeated_boss_ids=set(), seed=seed)
        assert not d.get("is_boss")


def test_roll_demon_day_100_forces_surt():
    d = roll_demon(day=100, defeated_boss_ids=set(), seed=0)
    assert d.get("is_boss") is True
    assert d.get("boss_id") == "surt"


def test_roll_demon_all_mid_dead_forces_surt():
    all_mid = {"belphegor","beelzebub","mammon","leviathan","asmodeus","satan","lucifer"}
    d = roll_demon(day=60, defeated_boss_ids=all_mid, seed=0)
    assert d.get("boss_id") == "surt"


def test_roll_demon_surt_dead_after_all_returns_regular():
    all_dead = {"belphegor","beelzebub","mammon","leviathan","asmodeus","satan","lucifer","surt"}
    d = roll_demon(day=100, defeated_boss_ids=all_dead, seed=0)
    assert not d.get("is_boss")


def test_roll_demon_boss_picks_weakest_alive():
    # day 90 → 100% chance, defeated={belphegor,beelzebub} → 맘몬 (next weakest)
    d = roll_demon(day=90, defeated_boss_ids={"belphegor","beelzebub"}, seed=0)
    assert d.get("boss_id") == "mammon"


def test_roll_demon_day40_eventually_spawns_boss():
    # 5% 확률 × 100 시드 → 1번 이상 보스 등장 확률 ≈ 99.4%
    spawned = any(
        roll_demon(day=40, defeated_boss_ids=set(), seed=s).get("is_boss")
        for s in range(100)
    )
    assert spawned

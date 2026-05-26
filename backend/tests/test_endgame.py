from app.endgame import detect_post_battle, detect_day_100, ENDINGS


def test_endings_have_all_required_fields():
    ids = {e["id"] for e in ENDINGS}
    assert ids == {"surt_killed", "lonely_demon", "forge_burns",
                   "retirement", "youth_blood", "weapons_broken"}
    for e in ENDINGS:
        assert "title" in e and "won" in e and "flavor" in e


def test_post_battle_surt_killed_highest_priority():
    p = {"heroes_died_total": 999, "weapons_destroyed_total": 999}
    assert detect_post_battle(p, {"surt"}) == "surt_killed"


def test_post_battle_youth_blood():
    p = {"heroes_died_total": 200, "weapons_destroyed_total": 0}
    assert detect_post_battle(p, set()) == "youth_blood"


def test_post_battle_weapons_broken():
    p = {"heroes_died_total": 0, "weapons_destroyed_total": 200}
    assert detect_post_battle(p, set()) == "weapons_broken"


def test_post_battle_youth_before_weapons():
    p = {"heroes_died_total": 200, "weapons_destroyed_total": 200}
    assert detect_post_battle(p, set()) == "youth_blood"


def test_post_battle_no_trigger():
    p = {"heroes_died_total": 199, "weapons_destroyed_total": 199}
    assert detect_post_battle(p, set()) is None


def test_day_100_with_surt_dead_returns_none():
    assert detect_day_100({}, {"surt"}) is None


def test_day_100_lonely_demon():
    mids = {"belphegor","beelzebub","mammon","leviathan","asmodeus","satan","lucifer"}
    assert detect_day_100({}, mids) == "lonely_demon"


def test_day_100_forge_burns_partial():
    assert detect_day_100({}, {"belphegor","beelzebub","mammon"}) == "forge_burns"


def test_day_100_retirement_zero_mid():
    assert detect_day_100({}, set()) == "retirement"


def test_day_100_forge_burns_single_kill():
    assert detect_day_100({}, {"belphegor"}) == "forge_burns"

from app.bosses import MID_BOSSES, FINAL_BOSS, weakest_alive, find_boss_by_id, is_boss_demon


def test_mid_bosses_count_and_order():
    assert len(MID_BOSSES) == 7
    diffs = [b["difficulty"] for b in MID_BOSSES]
    assert diffs == sorted(diffs), "MID_BOSSES must be sorted weakest first"


def test_all_bosses_have_required_fields():
    for b in MID_BOSSES + [FINAL_BOSS]:
        assert "boss_id" in b and "name" in b and "attribute" in b and "difficulty" in b


def test_weakest_alive_empty_defeated():
    assert weakest_alive(set())["boss_id"] == "belphegor"


def test_weakest_alive_first_killed():
    assert weakest_alive({"belphegor"})["boss_id"] == "beelzebub"


def test_weakest_alive_all_killed_returns_none():
    all_ids = {b["boss_id"] for b in MID_BOSSES}
    assert weakest_alive(all_ids) is None


def test_find_boss_by_id():
    assert find_boss_by_id("satan")["name"] == "사탄"
    assert find_boss_by_id("surt")["name"] == "수르트"
    assert find_boss_by_id("nonexistent") is None


def test_is_boss_demon_true_for_boss():
    assert is_boss_demon({"type": "사탄", "is_boss": True}) is True


def test_is_boss_demon_false_for_regular():
    assert is_boss_demon({"type": "고블린"}) is False

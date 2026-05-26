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

from app.hero_registry import generate_hero, schedule_return


def test_generate_hero_has_required_fields():
    h = generate_hero(seed=1)
    assert "name" in h and "job" in h
    assert h["str"] >= 5 and h["str"] <= 15
    assert h["mag"] >= 2 and h["mag"] <= 12
    assert h["status"] == "alive"
    assert 1 <= int(h["name"]) <= 1000


def test_schedule_return_survived():
    fields = schedule_return("survived", current_day=2)
    assert fields == {"status": "alive", "return_day": 5}


def test_schedule_return_fled():
    fields = schedule_return("fled", current_day=2)
    assert fields == {"status": "fled", "return_day": 9}


def test_schedule_return_died():
    fields = schedule_return("died", current_day=2)
    assert fields == {"status": "dead", "return_day": None}

import pytest
from app import combat
from app.combat import apply_outcomes, roll_demon


def test_decide_outcomes_returns_hero_opinion():
    hero = {"id": 1, "name": "테스트", "str": 5, "mag": 5, "level": 1}
    weapon = {"id": 1, "name": "검", "attack": 10, "sharpness": 30,
              "attribute": "화", "weapon_type": "검"}
    demon = {"id": "imp", "name": "임프", "difficulty": 1, "attribute": "수"}
    result = combat.decide_outcomes(hero, weapon, demon, seed=0)
    assert "hero_opinion" in result
    assert result["hero_opinion"] in {"want_better_weapon", "weapon_broke", "none"}


def test_decide_outcomes_weapon_broke_opinion_when_destroyed():
    hero = {"id": 1, "name": "테스트", "str": 5, "mag": 5, "level": 1}
    weapon = {"id": 1, "name": "검", "attack": 10, "sharpness": 0,
              "attribute": "화", "weapon_type": "검"}
    demon = {"id": "imp", "name": "임프", "difficulty": 10, "attribute": "수"}
    for s in range(50):
        result = combat.decide_outcomes(hero, weapon, demon, seed=s)
        if result.get("weapon") == "destroyed":
            assert result["hero_opinion"] == "weapon_broke"
            return
    pytest.fail("no destroyed weapon outcome found across 50 seeds")


def test_apply_outcomes_survived_killed_increases_rep():
    delta = apply_outcomes({"hero": "survived", "weapon": "preserved", "demon": "killed"})
    assert delta["reputation"] >= 2


def test_apply_outcomes_died_destroyed_decreases_rep():
    delta = apply_outcomes({"hero": "died", "weapon": "destroyed", "demon": "survived"})
    assert delta["reputation"] < 0


def test_apply_outcomes_neutral_outcomes_no_change():
    delta = apply_outcomes({"hero": "injured", "weapon": "preserved", "demon": "survived"})
    assert delta["reputation"] == 0


@pytest.mark.parametrize("day,lo,hi", [(1, 1, 10), (2, 3, 15), (3, 8, 22), (4, 14, 30), (5, 20, 40)])
def test_roll_demon_day_difficulty_range(day, lo, hi):
    for seed in range(30):
        d = roll_demon(day=day, seed=seed)
        assert lo <= d["difficulty"] <= hi, f"day={day} seed={seed} got {d['difficulty']}"


def test_decide_outcomes_attribute_advantage_helps():
    """Same hero/weapon/demon stats, but advantageous attribute → higher survival."""
    from app.combat import decide_outcomes
    hero = {"str": 10, "mag": 5}
    demon_fire = {"type": "x", "attribute": "불", "difficulty": 30}
    weapon_water = {"sharpness": 50, "rarity": 30, "attribute": "물"}  # 물→불 = 1.3
    weapon_fire  = {"sharpness": 50, "rarity": 30, "attribute": "불"}  # 동일속성 = 1.0
    survive_water = sum(
        1 for s in range(50)
        if decide_outcomes(hero, weapon_water, demon_fire, seed=s)["hero"] == "survived"
    )
    survive_fire = sum(
        1 for s in range(50)
        if decide_outcomes(hero, weapon_fire, demon_fire, seed=s)["hero"] == "survived"
    )
    assert survive_water > survive_fire, f"advantage={survive_water}, neutral={survive_fire}"

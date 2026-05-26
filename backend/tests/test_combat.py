import pytest
from app.combat import apply_outcomes, roll_demon


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

import pytest
from app.combat import apply_outcomes


def test_apply_outcomes_survived_killed_increases_rep():
    delta = apply_outcomes({"hero": "survived", "weapon": "preserved", "demon": "killed"})
    assert delta["reputation"] >= 2  # 생존 +1, 마왕 처치 +1


def test_apply_outcomes_died_destroyed_decreases_rep():
    delta = apply_outcomes({"hero": "died", "weapon": "destroyed", "demon": "survived"})
    assert delta["reputation"] < 0


def test_apply_outcomes_neutral_outcomes_no_change():
    delta = apply_outcomes({"hero": "injured", "weapon": "preserved", "demon": "survived"})
    assert delta["reputation"] == 0

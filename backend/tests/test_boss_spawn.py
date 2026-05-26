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

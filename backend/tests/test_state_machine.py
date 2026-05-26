import pytest
from app.state_machine import (
    next_phase, assert_phase, advance_to_next_day,
    INITIAL_PHASE, PHASES, PhaseError,
)


def test_initial_phase_is_forge_open():
    assert INITIAL_PHASE == "forge_open"


def test_phase_sequence():
    expected = [
        "forge_open", "hero1_negotiate", "hero1_battle",
        "merchant_negotiate",
        "hero2_negotiate", "hero2_battle",
        "forge_open_2",
        "hero3_negotiate", "hero3_battle",
        "day_summary",
    ]
    for i in range(len(expected) - 1):
        assert next_phase(expected[i]) == expected[i + 1]


def test_day_summary_next_goes_back_to_forge_open_marker():
    assert next_phase("day_summary") == "next_day"


def test_game_over_has_no_next():
    with pytest.raises(PhaseError):
        next_phase("game_over")


def test_assert_phase_match_and_mismatch():
    assert_phase("forge_open", "forge_open")
    with pytest.raises(PhaseError):
        assert_phase("hero1_negotiate", "forge_open")


def test_advance_to_next_day_increments_day_and_resets_phase():
    p = {"current_day": 1, "current_phase": "day_summary"}
    advance_to_next_day(p)
    assert p == {"current_day": 2, "current_phase": "forge_open"}


def test_advance_to_next_day_at_day_5_goes_to_game_over():
    p = {"current_day": 5, "current_phase": "day_summary"}
    advance_to_next_day(p)
    assert p == {"current_day": 5, "current_phase": "game_over"}

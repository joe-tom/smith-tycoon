import pytest
from app import state_machine as sm


def test_phases_simplified():
    assert sm.PHASES == ["forge_open", "visitor", "day_summary"]
    assert sm.INITIAL_PHASE == "forge_open"


def test_next_phase_normal():
    assert sm.next_phase("forge_open") == "visitor"
    assert sm.next_phase("visitor") == "day_summary"
    assert sm.next_phase("day_summary") == "next_day"


def test_next_phase_unknown_raises():
    with pytest.raises(sm.PhaseError):
        sm.next_phase("hero1_negotiate")
    with pytest.raises(sm.PhaseError):
        sm.next_phase("game_over")


def test_advance_to_next_day_increments():
    player = {"current_day": 1, "current_phase": "day_summary",
              "current_visitor_index": 5, "day_schedule": [{"kind": "merchant"}]}
    sm.advance_to_next_day(player)
    assert player["current_day"] == 2
    assert player["current_phase"] == "forge_open"
    assert player["current_visitor_index"] == 0
    assert player["day_schedule"] == []


def test_advance_to_next_day_game_over_at_max():
    player = {"current_day": sm.MAX_DAY, "current_phase": "day_summary",
              "current_visitor_index": 0, "day_schedule": []}
    sm.advance_to_next_day(player)
    assert player["current_phase"] == "game_over"


def test_advance_visitor_increments_index():
    player = {"current_phase": "visitor", "current_visitor_index": 0,
              "day_schedule": [{"kind": "new_hero"}, {"kind": "merchant"}, {"kind": "new_hero"}]}
    sm.advance_visitor(player)
    assert player["current_visitor_index"] == 1
    assert player["current_phase"] == "visitor"


def test_advance_visitor_last_slot_transitions_to_summary():
    player = {"current_phase": "visitor", "current_visitor_index": 1,
              "day_schedule": [{"kind": "merchant"}, {"kind": "new_hero"}]}
    sm.advance_visitor(player)
    assert player["current_phase"] == "day_summary"


def test_advance_visitor_outside_visitor_phase_raises():
    player = {"current_phase": "forge_open", "current_visitor_index": 0,
              "day_schedule": []}
    with pytest.raises(sm.PhaseError):
        sm.advance_visitor(player)


def test_assert_phase():
    sm.assert_phase("forge_open", "forge_open")
    with pytest.raises(sm.PhaseError):
        sm.assert_phase("forge_open", "visitor")

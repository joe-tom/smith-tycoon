import pytest
from app.state_machine import next_phase, assert_phase, INITIAL_PHASE, PhaseError


def test_initial_phase_is_forge_open():
    assert INITIAL_PHASE == "forge_open"


def test_phase_progression():
    assert next_phase("forge_open") == "hero_negotiate"
    assert next_phase("hero_negotiate") == "hero_battle"
    assert next_phase("hero_battle") == "done"


def test_next_phase_after_done_raises():
    with pytest.raises(PhaseError):
        next_phase("done")


def test_assert_phase_match():
    assert_phase("forge_open", "forge_open")  # no raise


def test_assert_phase_mismatch_raises():
    with pytest.raises(PhaseError):
        assert_phase("hero_negotiate", "forge_open")

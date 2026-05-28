import pytest
from app import scheduler


@pytest.mark.parametrize("rep,lo,hi", [
    (0, 3, 3), (5, 3, 3), (10, 3, 3),
    (11, 3, 5), (15, 3, 5), (20, 3, 5),
    (21, 5, 7), (30, 5, 7), (40, 5, 7),
    (41, 8, 10), (60, 8, 10),
    (61, 10, 10), (200, 10, 10),
])
def test_hero_slot_count_range(rep, lo, hi):
    counts = {scheduler.hero_slot_count(rep, seed=s) for s in range(50)}
    assert min(counts) >= lo
    assert max(counts) <= hi


def test_hero_slot_count_deterministic_same_seed():
    assert scheduler.hero_slot_count(15, seed=42) == scheduler.hero_slot_count(15, seed=42)


def test_schedule_seed_changes_per_day_and_player():
    assert scheduler.schedule_seed(1, 1) != scheduler.schedule_seed(1, 2)
    assert scheduler.schedule_seed(1, 1) != scheduler.schedule_seed(2, 1)


def test_resolve_day_survive_range():
    days = {scheduler.resolve_day_for("survive", 10, seed=s) for s in range(200)}
    assert days == {12, 13}


def test_resolve_day_injure_range():
    days = {scheduler.resolve_day_for("injure", 10, seed=s) for s in range(300)}
    assert days == {15, 16, 17}


def test_resolve_day_die_range():
    days = {scheduler.resolve_day_for("die", 10, seed=s) for s in range(200)}
    assert days == {11, 12}


def test_resolve_day_unknown_raises():
    with pytest.raises(ValueError):
        scheduler.resolve_day_for("nope", 10, seed=0)


def test_build_schedule_has_exactly_one_merchant():
    sched = scheduler.build_schedule(1, 5, reputation=0, pending_revisits=[])
    assert sum(1 for s in sched if s["kind"] == "merchant") == 1


def test_build_schedule_total_length_rep_zero():
    sched = scheduler.build_schedule(1, 5, reputation=0, pending_revisits=[])
    assert len(sched) == 4  # 3 hero + 1 merchant


def test_build_schedule_revisits_take_priority():
    revisits = [
        {"id": 100, "hero_id": 11, "kind": "revisit_survive"},
        {"id": 101, "hero_id": 12, "kind": "revisit_injure"},
    ]
    sched = scheduler.build_schedule(1, 5, reputation=0, pending_revisits=revisits)
    kinds = [s["kind"] for s in sched]
    assert kinds.count("returning_hero") == 2
    assert kinds.count("new_hero") == 1
    assert kinds.count("merchant") == 1


def test_build_schedule_overflow_returns_postponed_ids():
    revisits = [
        {"id": 200 + i, "hero_id": 20 + i, "kind": "revisit_survive"} for i in range(5)
    ]
    sched = scheduler.build_schedule(1, 5, reputation=0, pending_revisits=revisits)
    returning = [s for s in sched if s["kind"] == "returning_hero"]
    assert len(returning) == 3
    postponed = scheduler.postponed_outcome_ids(revisits, returning)
    assert set(postponed) == {203, 204}


def test_build_schedule_deterministic():
    a = scheduler.build_schedule(1, 5, reputation=30, pending_revisits=[])
    b = scheduler.build_schedule(1, 5, reputation=30, pending_revisits=[])
    assert a == b

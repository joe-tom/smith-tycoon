import pytest
from app.missions import tax


def test_plan_warning_on_day_3():
    rows = tax.plan({"id": 1}, 3)
    assert len(rows) == 1
    assert rows[0]["kind"] == "tax" and rows[0]["phase"] == "warning"
    assert rows[0]["due_day"] == 3


def test_plan_collect_on_day_10():
    rows = tax.plan({"id": 1}, 10)
    assert any(r["phase"] == "collect" and r["due_day"] == 10
               and r["payload"]["amount"] == 1000 for r in rows)


def test_plan_no_collect_on_day_100():
    rows = tax.plan({"id": 1}, 100)
    assert rows == []


def test_plan_no_op_on_other_days():
    assert tax.plan({"id": 1}, 5) == []
    assert tax.plan({"id": 1}, 11) == []


def test_evaluate_warning_pending_after_due():
    mission = {"id": 1, "kind": "tax", "phase": "warning", "due_day": 3, "status": "pending"}
    assert tax.evaluate({"id": 1, "current_day": 5}, 5, mission) == ("pending", None)


def test_evaluate_collect_due_passed_pending_fails():
    mission = {"id": 1, "kind": "tax", "phase": "collect", "due_day": 10,
               "status": "pending", "payload": {"amount": 1000}}
    status, ending = tax.evaluate({"id": 1, "current_day": 11}, 11, mission)
    assert status == "failed"
    assert ending == "mission_tax_unpaid"


def test_evaluate_collect_done_no_ending():
    mission = {"id": 1, "kind": "tax", "phase": "collect", "due_day": 10,
               "status": "done", "payload": {"amount": 1000}}
    assert tax.evaluate({"id": 1, "current_day": 11}, 11, mission) == ("done", None)


def test_slot_for_collect_includes_amount():
    s = tax.slot_for({"id": 7, "kind": "tax", "phase": "collect",
                       "payload": {"amount": 1000}})
    assert s == {"kind": "mission_npc", "mission_id": 7, "mission_kind": "tax",
                 "phase": "collect", "amount": 1000}


def test_on_action_warning_ack_marks_done(fake_repo, monkeypatch):
    monkeypatch.setattr(tax, "repo", fake_repo)
    fake_repo.players[1] = {"id": 1, "gold": 5000, "current_day": 3, "current_phase": "visitor"}
    m = fake_repo.insert_mission({"player_id": 1, "kind": "tax", "phase": "warning",
                                   "due_day": 3, "payload": {}})
    tax.on_action(fake_repo.players[1], m, "ack")
    assert fake_repo.get_mission(m["id"])["status"] == "done"


def test_on_action_collect_pay_success(fake_repo, monkeypatch):
    monkeypatch.setattr(tax, "repo", fake_repo)
    fake_repo.players[1] = {"id": 1, "gold": 5000, "current_day": 10, "current_phase": "visitor"}
    m = fake_repo.insert_mission({"player_id": 1, "kind": "tax", "phase": "collect",
                                   "due_day": 10, "payload": {"amount": 1000}})
    tax.on_action(fake_repo.players[1], m, "pay")
    assert fake_repo.players[1]["gold"] == 4000
    assert fake_repo.get_mission(m["id"])["status"] == "done"


def test_on_action_collect_pay_insufficient_raises(fake_repo, monkeypatch):
    monkeypatch.setattr(tax, "repo", fake_repo)
    fake_repo.players[1] = {"id": 1, "gold": 500, "current_day": 10, "current_phase": "visitor"}
    m = fake_repo.insert_mission({"player_id": 1, "kind": "tax", "phase": "collect",
                                   "due_day": 10, "payload": {"amount": 1000}})
    with pytest.raises(ValueError):
        tax.on_action(fake_repo.players[1], m, "pay")
    assert fake_repo.players[1]["gold"] == 500


def test_on_action_collect_skip_returns_ending(fake_repo, monkeypatch):
    monkeypatch.setattr(tax, "repo", fake_repo)
    fake_repo.players[1] = {"id": 1, "gold": 5000, "current_day": 10, "current_phase": "visitor"}
    m = fake_repo.insert_mission({"player_id": 1, "kind": "tax", "phase": "collect",
                                   "due_day": 10, "payload": {"amount": 1000}})
    result = tax.on_action(fake_repo.players[1], m, "skip")
    assert result["ending_kind"] == "mission_tax_unpaid"
    assert fake_repo.get_mission(m["id"])["status"] == "failed"

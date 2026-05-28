import pytest
from app.missions import league_chief as lc


def test_spawn_day_in_range_and_deterministic():
    days = {lc.spawn_day(player_id=pid) for pid in range(50)}
    assert all(11 <= d <= 15 for d in days)
    assert lc.spawn_day(7) == lc.spawn_day(7)


def test_plan_inserts_challenge_on_spawn_day():
    pid = 1
    spawn = lc.spawn_day(pid)
    rows = lc.plan({"id": pid}, spawn)
    assert len(rows) == 1
    r = rows[0]
    assert r["kind"] == "league_chief" and r["phase"] == "challenge"
    assert r["payload"]["threshold"] == 50
    assert r["payload"]["deadline"] == spawn + 3


def test_plan_no_op_other_days():
    pid = 1
    spawn = lc.spawn_day(pid)
    assert lc.plan({"id": pid}, spawn - 1) == []
    assert lc.plan({"id": pid}, spawn + 1) == []


def test_evaluate_challenge_condition_met_inserts_praise(fake_repo, monkeypatch):
    monkeypatch.setattr(lc, "repo", fake_repo)
    pid = 1
    fake_repo.players[pid] = {"id": pid, "reputation": 50, "current_day": 13}
    mission = {"id": 5, "player_id": pid, "kind": "league_chief", "phase": "challenge",
               "due_day": 12, "status": "pending",
               "payload": {"threshold": 50, "deadline": 15}}
    status, ending = lc.evaluate(fake_repo.players[pid], 13, mission)
    assert status == "condition_met"
    assert ending is None
    praise = [m for m in fake_repo.missions
              if m["kind"] == "league_chief" and m["phase"] == "praise"]
    assert len(praise) == 1
    assert praise[0]["due_day"] == 14


def test_evaluate_challenge_under_threshold_keeps_pending(fake_repo, monkeypatch):
    monkeypatch.setattr(lc, "repo", fake_repo)
    fake_repo.players[1] = {"id": 1, "reputation": 30, "current_day": 13}
    mission = {"id": 5, "player_id": 1, "kind": "league_chief", "phase": "challenge",
               "due_day": 12, "status": "pending",
               "payload": {"threshold": 50, "deadline": 15}}
    status, ending = lc.evaluate(fake_repo.players[1], 13, mission)
    assert status == "pending"
    assert ending is None


def test_evaluate_challenge_deadline_passed_fails(fake_repo, monkeypatch):
    monkeypatch.setattr(lc, "repo", fake_repo)
    fake_repo.players[1] = {"id": 1, "reputation": 30, "current_day": 16}
    mission = {"id": 5, "player_id": 1, "kind": "league_chief", "phase": "challenge",
               "due_day": 12, "status": "pending",
               "payload": {"threshold": 50, "deadline": 15}}
    status, ending = lc.evaluate(fake_repo.players[1], 16, mission)
    assert status == "failed"
    assert ending == "mission_league_failed"


def test_on_action_challenge_ack_keeps_pending(fake_repo, monkeypatch):
    monkeypatch.setattr(lc, "repo", fake_repo)
    fake_repo.players[1] = {"id": 1, "reputation": 30, "current_day": 12, "current_phase": "visitor"}
    m = fake_repo.insert_mission({"player_id": 1, "kind": "league_chief", "phase": "challenge",
                                   "due_day": 12, "payload": {"threshold": 50, "deadline": 15}})
    lc.on_action(fake_repo.players[1], m, "ack")
    assert fake_repo.get_mission(m["id"])["status"] == "pending"


def test_on_action_praise_ack_marks_done(fake_repo, monkeypatch):
    monkeypatch.setattr(lc, "repo", fake_repo)
    fake_repo.players[1] = {"id": 1, "reputation": 60, "current_day": 14, "current_phase": "visitor"}
    m = fake_repo.insert_mission({"player_id": 1, "kind": "league_chief", "phase": "praise",
                                   "due_day": 14, "payload": {}})
    lc.on_action(fake_repo.players[1], m, "ack")
    assert fake_repo.get_mission(m["id"])["status"] == "done"

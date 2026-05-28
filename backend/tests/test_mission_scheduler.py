from app.missions import scheduler


def test_advance_plans_warning_day_3(fake_repo, monkeypatch):
    monkeypatch.setattr(scheduler, "repo", fake_repo)
    from app.missions import tax as tax_mod, league_chief as lc_mod
    monkeypatch.setattr(tax_mod, "repo", fake_repo)
    monkeypatch.setattr(lc_mod, "repo", fake_repo)

    fake_repo.players[1] = {"id": 1, "current_day": 3, "reputation": 0,
                             "current_phase": "forge_open", "gold": 5000,
                             "ending_kind": None}
    scheduler.advance(fake_repo.players[1])
    assert any(m["kind"] == "tax" and m["phase"] == "warning"
               for m in fake_repo.missions)


def test_advance_ending_triggered_on_unpaid_tax(fake_repo, monkeypatch):
    monkeypatch.setattr(scheduler, "repo", fake_repo)
    from app.missions import tax as tax_mod, league_chief as lc_mod
    from app import endgame
    monkeypatch.setattr(tax_mod, "repo", fake_repo)
    monkeypatch.setattr(lc_mod, "repo", fake_repo)
    monkeypatch.setattr(endgame, "repo", fake_repo)

    fake_repo.players[1] = {"id": 1, "current_day": 11, "reputation": 0,
                             "current_phase": "forge_open", "gold": 500,
                             "ending_kind": None}
    fake_repo.insert_mission({"player_id": 1, "kind": "tax", "phase": "collect",
                               "due_day": 10, "status": "pending",
                               "payload": {"amount": 1000}})
    scheduler.advance(fake_repo.players[1])
    assert fake_repo.players[1]["ending_kind"] == "mission_tax_unpaid"


def test_today_slots_returns_due_today_missions(fake_repo, monkeypatch):
    monkeypatch.setattr(scheduler, "repo", fake_repo)
    fake_repo.insert_mission({"player_id": 1, "kind": "tax", "phase": "warning",
                               "due_day": 3, "status": "pending", "payload": {}})
    fake_repo.insert_mission({"player_id": 1, "kind": "tax", "phase": "collect",
                               "due_day": 10, "status": "pending",
                               "payload": {"amount": 1000}})
    slots = scheduler.today_slots(player_id=1, day=3)
    assert len(slots) == 1
    assert slots[0]["mission_kind"] == "tax"
    assert slots[0]["phase"] == "warning"

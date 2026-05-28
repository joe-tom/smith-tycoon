from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def patched_app(fake_repo):
    from app import repo as real_repo
    from app.api import mail as mail_api
    from app import auth as auth_mod
    fake_repo.players[1] = {"id": 1, "nickname": "tester", "current_day": 5,
                            "current_phase": "forge_open", "current_visitor_index": 0,
                            "day_schedule": [], "reputation": 0, "gold": 0,
                            "craft_power": 0, "effort": 50, "heroes_died_total": 0,
                            "weapons_destroyed_total": 0, "ending_kind": None}
    fake_repo.pending_outcomes.append({
        "id": 99, "player_id": 1, "hero_id": 1, "depart_day": 1, "resolve_day": 5,
        "kind": "death_mail", "outcome_json": {"hero": "died"},
        "weapon_snapshot": {}, "consumed": False,
    })
    fake_repo._pending_seq = 99

    fake_repo.get_or_create_player_by_nickname = lambda nick: fake_repo.players[1]
    with patch.object(mail_api, "repo", fake_repo), \
         patch.object(auth_mod, "repo", fake_repo):
        from app.main import app
        yield TestClient(app), fake_repo


def test_death_mail_ack_marks_consumed(patched_app):
    client, fake = patched_app
    r = client.post("/mail/99/ack", headers={"X-Player-Nickname": "tester"})
    assert r.status_code == 200, r.text
    assert any(p["id"] == 99 and p["consumed"] for p in fake.pending_outcomes)


def test_mail_ack_not_found(patched_app):
    client, _ = patched_app
    r = client.post("/mail/9999/ack", headers={"X-Player-Nickname": "tester"})
    assert r.status_code == 404


def test_mail_ack_wrong_kind(patched_app):
    client, fake = patched_app
    fake.pending_outcomes.append({
        "id": 100, "player_id": 1, "hero_id": 1, "depart_day": 1, "resolve_day": 5,
        "kind": "revisit_survive", "outcome_json": {}, "weapon_snapshot": {}, "consumed": False,
    })
    r = client.post("/mail/100/ack", headers={"X-Player-Nickname": "tester"})
    assert r.status_code == 400

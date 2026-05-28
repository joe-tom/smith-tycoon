from unittest.mock import patch
from app import pending_outcomes as po


def _hero(**kw):
    return {"id": 1, "name": "H", "str": 5, "mag": 5, "level": 1, **kw}


def _weapon(**kw):
    return {"id": 10, "name": "검", "attack": 10, "sharpness": 30,
            "attribute": "화", "weapon_type": "검", **kw}


def _demon(**kw):
    return {"id": "imp", "name": "임프", "difficulty": 1, "attribute": "수", **kw}


def test_dispatch_writes_pending_and_deletes_weapon(fake_repo):
    fake_repo.weapons.append(_weapon())
    with patch.object(po, "repo", fake_repo):
        player = {"id": 1, "current_day": 10}
        result = po.dispatch_hero(player, _hero(), _weapon(), _demon())
    assert "outcome_id" in result
    assert result["outcome"]["hero"] in {"survived", "injured", "died"}
    weapon10 = next(w for w in fake_repo.weapons if w["id"] == 10)
    assert weapon10["owner"] == "dispatched"
    assert len(fake_repo.pending_outcomes) == 1
    pending = fake_repo.pending_outcomes[0]
    assert pending["depart_day"] == 10
    assert pending["resolve_day"] >= 11
    assert pending["kind"] in {"revisit_survive", "revisit_injure", "death_mail"}
    assert pending["weapon_snapshot"]["id"] == 10


def test_dispatch_deterministic(fake_repo):
    with patch.object(po, "repo", fake_repo):
        player = {"id": 1, "current_day": 5}
        fake_repo.weapons.append(_weapon())
        a = po.dispatch_hero(player, _hero(), _weapon(), _demon())
        fake_repo.pending_outcomes.clear()
        fake_repo.weapons.append(_weapon())
        b = po.dispatch_hero(player, _hero(), _weapon(), _demon())
    assert a["outcome"] == b["outcome"]
    assert a["resolve_day"] == b["resolve_day"]


def test_dispatch_without_weapon(fake_repo):
    with patch.object(po, "repo", fake_repo):
        player = {"id": 1, "current_day": 5}
        result = po.dispatch_hero(player, _hero(), None, _demon())
    assert "outcome_id" in result
    pending = fake_repo.pending_outcomes[0]
    assert pending["weapon_snapshot"] == {}

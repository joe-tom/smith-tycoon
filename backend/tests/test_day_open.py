from unittest.mock import patch
from app import day_open


def _heroes_for_today_stub(heroes):
    def _stub(player_id, day, count=3):
        return heroes[:count]
    return _stub


def test_prepare_day_builds_schedule_with_new_heroes(fake_repo):
    player = {"id": 1, "current_day": 3, "reputation": 0, "current_phase": "forge_open"}
    fake_repo.players[1] = player
    heroes = [{"id": 100, "name": "A"}, {"id": 101, "name": "B"}, {"id": 102, "name": "C"}]
    with patch.object(day_open, "repo", fake_repo), \
         patch.object(day_open, "hero_registry") as mock_hr:
        mock_hr.heroes_for_today.side_effect = _heroes_for_today_stub(heroes)
        result = day_open.prepare_day(player)
    assert len(result["schedule"]) == 4
    hero_ids = [s["hero_id"] for s in result["schedule"] if s["kind"] == "new_hero"]
    assert set(hero_ids) == {100, 101, 102}
    assert result["death_mails"] == []


def test_prepare_day_extracts_death_mails(fake_repo):
    fake_repo.pending_outcomes.append({
        "id": 5, "player_id": 1, "hero_id": 50, "depart_day": 1, "resolve_day": 3,
        "kind": "death_mail", "outcome_json": {"hero": "died"},
        "weapon_snapshot": {"name": "검"}, "consumed": False,
    })
    fake_repo._pending_seq = 5
    player = {"id": 1, "current_day": 3, "reputation": 0, "current_phase": "forge_open"}
    fake_repo.players[1] = player
    heroes = [{"id": 100, "name": "A"}, {"id": 101, "name": "B"}, {"id": 102, "name": "C"}]
    with patch.object(day_open, "repo", fake_repo), \
         patch.object(day_open, "hero_registry") as mock_hr:
        mock_hr.heroes_for_today.side_effect = _heroes_for_today_stub(heroes)
        result = day_open.prepare_day(player)
    assert len(result["death_mails"]) == 1
    assert result["death_mails"][0]["id"] == 5


def test_prepare_day_revisits_take_priority(fake_repo):
    # 평판 0 → 3 슬롯, revisit 2개 → 신규 1개
    for i in range(2):
        fake_repo.pending_outcomes.append({
            "id": 10 + i, "player_id": 1, "hero_id": 20 + i, "depart_day": 1,
            "resolve_day": 3, "kind": "revisit_survive",
            "outcome_json": {"hero": "survived"}, "weapon_snapshot": {}, "consumed": False,
        })
    player = {"id": 1, "current_day": 3, "reputation": 0, "current_phase": "forge_open"}
    fake_repo.players[1] = player
    with patch.object(day_open, "repo", fake_repo), \
         patch.object(day_open, "hero_registry") as mock_hr:
        mock_hr.heroes_for_today.side_effect = _heroes_for_today_stub([{"id": 999, "name": "X"}])
        result = day_open.prepare_day(player)
    kinds = [s["kind"] for s in result["schedule"]]
    assert kinds.count("returning_hero") == 2
    assert kinds.count("new_hero") == 1
    assert kinds.count("merchant") == 1


def test_prepare_day_postpones_overflow_revisits(fake_repo):
    for i in range(5):
        fake_repo.pending_outcomes.append({
            "id": 200 + i, "player_id": 1, "hero_id": 20 + i, "depart_day": 1,
            "resolve_day": 3, "kind": "revisit_survive",
            "outcome_json": {"hero": "survived"}, "weapon_snapshot": {}, "consumed": False,
        })
    player = {"id": 1, "current_day": 3, "reputation": 0, "current_phase": "forge_open"}
    fake_repo.players[1] = player
    with patch.object(day_open, "repo", fake_repo), \
         patch.object(day_open, "hero_registry") as mock_hr:
        mock_hr.heroes_for_today.side_effect = _heroes_for_today_stub([])
        day_open.prepare_day(player)
    postponed = [p for p in fake_repo.pending_outcomes if p["resolve_day"] == 4]
    assert len(postponed) == 2


def test_prepare_day_writes_to_player(fake_repo):
    player = {"id": 1, "current_day": 3, "reputation": 0, "current_phase": "forge_open"}
    fake_repo.players[1] = player
    with patch.object(day_open, "repo", fake_repo), \
         patch.object(day_open, "hero_registry") as mock_hr:
        mock_hr.heroes_for_today.side_effect = _heroes_for_today_stub(
            [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}, {"id": 3, "name": "C"}]
        )
        day_open.prepare_day(player)
    saved = fake_repo.players[1]
    assert saved["current_visitor_index"] == 0
    assert len(saved["day_schedule"]) == 4

import pytest
from app import combat


def _setup(fake_repo, monkeypatch, hero_outcome, weapon_outcome, demon_outcome):
    fake_repo.heroes.append({
        "id": 1, "player_id": 1, "name": "H", "job": "검사", "str": 5, "mag": 5,
        "level": 1, "personality_tags": [], "affinity": 0, "history": [],
        "loot_pending": [], "lore": [], "status": "alive", "visit_count": 1,
        "held_weapon_id": None,
    })
    fake_repo.weapons.append({
        "id": 10, "player_id": 1, "name": "검", "attack": 10, "sharpness": 30,
        "attribute": "화", "type": "검", "owner": "player", "rarity": 0,
        "materials_used": [{"category": "일반"}],
    })
    fake_repo.materials = [{"id": 100, "category": "일반", "name": "철", "base_price": 50}]
    fake_repo.players[1] = {"id": 1, "current_day": 1, "current_phase": "visitor",
                             "reputation": 0, "heroes_died_total": 0,
                             "weapons_destroyed_total": 0}

    monkeypatch.setattr(combat, "repo", fake_repo)
    from app import pending_outcomes as po, loot_table
    monkeypatch.setattr(po, "repo", fake_repo)
    monkeypatch.setattr(loot_table, "repo", fake_repo)
    monkeypatch.setattr(combat, "roll_demon",
                        lambda day, defeated_boss_ids=None: {
                            "id": "imp", "name": "임프", "difficulty": 1, "attribute": "수",
                            "type": "imp"
                        })
    monkeypatch.setattr(combat, "decide_outcomes",
                        lambda h, w, d, seed=None: {
                            "hero": hero_outcome, "weapon": weapon_outcome,
                            "demon": demon_outcome, "hero_opinion": "none",
                        })


@pytest.mark.asyncio
async def test_dispatch_adds_loot_on_survive_kill(fake_repo, monkeypatch):
    _setup(fake_repo, monkeypatch, "survived", "preserved", "killed")
    await combat.dispatch_async_battle(fake_repo.players[1], hero_id=1, weapon_id=10)
    h = fake_repo.get_hero(1)
    assert len(h["loot_pending"]) >= 1
    assert "loot" in fake_repo.pending_outcomes[-1]["outcome_json"]


@pytest.mark.asyncio
async def test_dispatch_no_loot_on_die(fake_repo, monkeypatch):
    _setup(fake_repo, monkeypatch, "died", "destroyed", "survived")
    await combat.dispatch_async_battle(fake_repo.players[1], hero_id=1, weapon_id=10)
    h = fake_repo.get_hero(1)
    assert h["loot_pending"] == []


@pytest.mark.asyncio
async def test_dispatch_no_loot_when_demon_fled(fake_repo, monkeypatch):
    _setup(fake_repo, monkeypatch, "survived", "preserved", "fled")
    await combat.dispatch_async_battle(fake_repo.players[1], hero_id=1, weapon_id=10)
    h = fake_repo.get_hero(1)
    assert h["loot_pending"] == []

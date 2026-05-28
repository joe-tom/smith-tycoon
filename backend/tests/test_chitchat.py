import pytest
from app import chitchat


@pytest.mark.asyncio
async def test_converse_appends_lore(fake_repo, monkeypatch):
    hero = {"id": 1, "name": "H", "job": "검사", "personality_tags": [],
            "affinity": 0, "history": [], "lore": []}
    fake_repo.heroes.append(hero)
    monkeypatch.setattr(chitchat, "repo", fake_repo)
    result = await chitchat.converse({"id": 1, "current_day": 5}, hero, "안녕")
    assert "lore_text" in result
    h = fake_repo.get_hero(1)
    assert len(h["lore"]) == 1
    assert h["lore"][0]["day"] == 5


@pytest.mark.asyncio
async def test_converse_blocked_by_negative_affinity(fake_repo, monkeypatch):
    hero = {"id": 1, "name": "H", "job": "검사", "personality_tags": [],
            "affinity": -10, "history": [], "lore": []}
    monkeypatch.setattr(chitchat, "repo", fake_repo)
    with pytest.raises(ValueError):
        await chitchat.converse({"id": 1, "current_day": 1}, hero, "")


@pytest.mark.asyncio
async def test_converse_caps_lore_at_20(fake_repo, monkeypatch):
    hero = {"id": 1, "name": "H", "job": "검사", "personality_tags": [],
            "affinity": 0, "history": [],
            "lore": [{"day": d, "text": f"old {d}"} for d in range(20)]}
    fake_repo.heroes.append(hero)
    monkeypatch.setattr(chitchat, "repo", fake_repo)
    await chitchat.converse({"id": 1, "current_day": 99}, hero, "")
    h = fake_repo.get_hero(1)
    assert len(h["lore"]) == 20
    assert h["lore"][-1]["day"] == 99
    assert h["lore"][0]["day"] == 1

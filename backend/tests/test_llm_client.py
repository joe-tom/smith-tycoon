import pytest
from app.llm.client import complete_json


@pytest.mark.asyncio
async def test_complete_json_returns_fixture():
    result = await complete_json("forge_name", "forge_name_basic",
                                 weapon_type="양손검",
                                 materials=[{"name": "원목", "category": "일반"}])
    assert result == {"name": "원목 양손검"}


@pytest.mark.asyncio
async def test_complete_json_battle_fixture():
    result = await complete_json("battle", "battle_basic",
                                 hero={"name": "라엘", "job": "검사", "str": 10, "mag": 3},
                                 weapon={"name": "원목 양손검", "sharpness": 50, "rarity": 30},
                                 demon={"type": "고블린", "difficulty": 5})
    assert result["outcomes"]["hero"] == "survived"
    assert "라엘" in result["script"]

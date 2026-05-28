from unittest.mock import patch
from app import loot_table


def _demon(difficulty=3, is_boss=False, boss_id=None, **kw):
    return {"difficulty": difficulty, "is_boss": is_boss, "boss_id": boss_id, **kw}


def _materials():
    return [
        {"id": 1, "category": "일반", "name": "철"},
        {"id": 2, "category": "일반", "name": "원목"},
        {"id": 3, "category": "일반", "name": "가죽"},
        {"id": 4, "category": "이상한", "name": "녹슨못"},
        {"id": 5, "category": "이상한", "name": "버려진끈"},
        {"id": 6, "category": "특수", "name": "마정석"},
        {"id": 7, "category": "전설", "name": "화염정수"},
    ]


def _by_cat(mats):
    return lambda cat: [m for m in mats if m["category"] == cat]


@patch("app.loot_table.repo")
def test_low_difficulty_common_only(mock_repo):
    mats = _materials()
    mock_repo.list_materials_by_category.side_effect = _by_cat(mats)
    loot = loot_table.roll_loot(_demon(difficulty=2), seed=42)
    cats = {next(m for m in mats if m["id"] == it["material_id"])["category"] for it in loot}
    assert cats == {"일반"}
    assert 1 <= len(loot) <= 2


@patch("app.loot_table.repo")
def test_mid_difficulty_uncommon_possible(mock_repo):
    mats = _materials()
    mock_repo.list_materials_by_category.side_effect = _by_cat(mats)
    seen = False
    for s in range(50):
        loot = loot_table.roll_loot(_demon(difficulty=5), seed=s)
        cats = {next(m for m in mats if m["id"] == it["material_id"])["category"] for it in loot}
        if "이상한" in cats:
            seen = True
            break
    assert seen


@patch("app.loot_table.repo")
def test_high_difficulty_rare_possible(mock_repo):
    mats = _materials()
    mock_repo.list_materials_by_category.side_effect = _by_cat(mats)
    seen = False
    for s in range(50):
        loot = loot_table.roll_loot(_demon(difficulty=8), seed=s)
        cats = {next(m for m in mats if m["id"] == it["material_id"])["category"] for it in loot}
        if "특수" in cats:
            seen = True
            break
    assert seen


@patch("app.loot_table.repo")
def test_boss_signature(mock_repo):
    mats = _materials()
    mock_repo.list_materials_by_category.side_effect = _by_cat(mats)
    loot = loot_table.roll_loot(_demon(difficulty=10, is_boss=True, boss_id="surt"), seed=1)
    names = {next(m for m in mats if m["id"] == it["material_id"])["name"] for it in loot}
    assert "화염정수" in names


@patch("app.loot_table.repo")
def test_deterministic(mock_repo):
    mats = _materials()
    mock_repo.list_materials_by_category.side_effect = _by_cat(mats)
    a = loot_table.roll_loot(_demon(difficulty=5), seed=99)
    b = loot_table.roll_loot(_demon(difficulty=5), seed=99)
    assert a == b


@patch("app.loot_table.repo")
def test_empty_category_returns_no_item(mock_repo):
    mock_repo.list_materials_by_category.side_effect = lambda cat: []
    loot = loot_table.roll_loot(_demon(difficulty=3), seed=1)
    assert loot == []

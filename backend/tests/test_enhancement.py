import pytest
from app.enhancement import roll_delta, apply_to_weapon


@pytest.mark.parametrize("category,sharp_min,sharp_max,rar_min,rar_max", [
    ("일반",   1, 3, 0, 2),
    ("이상한", 0, 2, 0, 2),
    ("특수",   3, 7, 2, 5),
    ("전설",   7, 15, 5, 12),
])
def test_roll_delta_per_category(category, sharp_min, sharp_max, rar_min, rar_max):
    for seed in range(30):
        d = roll_delta([{"category": category, "qty": 1}], seed=seed)
        assert sharp_min <= d["sharpness"] <= sharp_max
        assert rar_min <= d["rarity"] <= rar_max


def test_roll_delta_sums_multiple_materials():
    for seed in range(10):
        d = roll_delta([{"category": "일반", "qty": 1}, {"category": "특수", "qty": 1}], seed=seed)
        assert d["sharpness"] >= 1 + 3
        assert d["rarity"] >= 0 + 2


def test_apply_to_weapon_caps_at_100():
    w = {"sharpness": 95, "rarity": 90, "enhancement_level": 0, "materials_used": []}
    new = apply_to_weapon(w, {"sharpness": 10, "rarity": 15},
                          used_materials=[{"category": "전설", "qty": 1}])
    assert new["sharpness"] == 100
    assert new["rarity"] == 100
    assert new["enhancement_level"] == 1
    assert new["materials_used"][-1]["action"] == "enhance"
    assert new["materials_used"][-1]["delta"] == {"sharpness": 10, "rarity": 15}


def test_apply_to_weapon_appends_to_existing_materials_used():
    w = {"sharpness": 30, "rarity": 20, "enhancement_level": 2,
         "materials_used": [{"name": "철덩이", "qty": 2}]}
    new = apply_to_weapon(w, {"sharpness": 3, "rarity": 1},
                          used_materials=[{"category": "일반", "qty": 1}])
    assert new["enhancement_level"] == 3
    assert len(new["materials_used"]) == 2
    assert new["materials_used"][0]["name"] == "철덩이"

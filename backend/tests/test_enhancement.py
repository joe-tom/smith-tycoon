import pytest
from app.enhancement import roll_delta, apply_to_weapon, quality_score, _max_delta


# --- cap (스탯의 1.4배 = +40%) ---

@pytest.mark.parametrize("current,expected_max_delta", [
    (10, 4),     # 10*0.4=4
    (30, 12),    # 30*0.4=12
    (50, 20),
    (100, 40),
    (0, 3),      # MIN_DELTA_FLOOR
    (5, 3),      # max(3, int(2)) = 3
])
def test_max_delta_caps_at_40pct_with_min_floor(current, expected_max_delta):
    assert _max_delta(current) == expected_max_delta


# --- quality_score ---

def test_quality_score_floor():
    assert quality_score([]) == 0.2  # QUALITY_FLOOR


def test_quality_score_normal_single():
    assert quality_score([{"category": "일반", "qty": 1}]) == 0.2  # 0.1 but floored


def test_quality_score_legendary_caps_at_1():
    assert quality_score([{"category": "전설", "qty": 5}]) == 1.0


def test_quality_score_sums_materials():
    # 특수×1 (0.5) + 일반×3 (0.3) = 0.8
    assert quality_score([{"category": "특수", "qty": 1},
                          {"category": "일반", "qty": 3}]) == 0.8


# --- roll_delta cap respect ---

def test_roll_delta_respects_cap_for_high_quality():
    weapon = {"sharpness": 30, "rarity": 20}
    for seed in range(20):
        d = roll_delta(weapon, [{"category": "전설", "qty": 1}], seed=seed)
        assert 0 <= d["sharpness"] <= _max_delta(30)  # ≤ 12
        assert 0 <= d["rarity"] <= _max_delta(20)     # ≤ 8


def test_roll_delta_low_quality_gives_smaller_deltas():
    weapon = {"sharpness": 50, "rarity": 50}
    low = []
    high = []
    for seed in range(50):
        d_low = roll_delta(weapon, [{"category": "일반", "qty": 1}], seed=seed)
        d_high = roll_delta(weapon, [{"category": "전설", "qty": 1}], seed=seed)
        low.append(d_low["sharpness"])
        high.append(d_high["sharpness"])
    # 평균적으로 전설이 더 큰 delta를 만들어야 함
    assert sum(high) / len(high) > sum(low) / len(low)


def test_roll_delta_with_zero_stat_uses_min_floor():
    # current=0이어도 MIN_DELTA_FLOOR(=3) 덕분에 progression 가능
    weapon = {"sharpness": 0, "rarity": 0}
    for seed in range(20):
        d = roll_delta(weapon, [{"category": "전설", "qty": 1}], seed=seed)
        assert 0 <= d["sharpness"] <= 3
        assert 0 <= d["rarity"] <= 3


# --- apply_to_weapon (변경 없음) ---

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

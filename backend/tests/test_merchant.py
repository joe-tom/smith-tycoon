from app.merchant import generate_today, bundle_market_price


def test_bundle_market_price_materials_only():
    bundle = {
        "materials": [
            {"material_id": 1, "qty": 2, "name": "x", "category": "일반", "base_price": 50},
            {"material_id": 2, "qty": 1, "name": "y", "category": "특수", "base_price": 800},
        ],
        "weapon": None,
    }
    assert bundle_market_price(bundle) == 50 * 2 + 800 * 1


def test_bundle_market_price_with_weapon():
    bundle = {
        "materials": [{"material_id": 1, "qty": 1, "name": "x", "category": "일반", "base_price": 50}],
        "weapon": {"asking_price": 500},
    }
    assert bundle_market_price(bundle) == 50 + 500


def test_generate_today_deterministic_with_seed():
    a = generate_today(day=1, seed=42)
    b = generate_today(day=1, seed=42)
    assert a == b


def test_generate_today_has_4_to_6_materials():
    for seed in range(10):
        bundle = generate_today(day=1, seed=seed)
        assert 4 <= len(bundle["materials"]) <= 6

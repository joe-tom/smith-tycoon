import pytest
from app.negotiation import clamp_price, market_price


def test_clamp_price_lower_bound():
    assert clamp_price(10, base=1000) == 100   # 0.1배 하한


def test_clamp_price_upper_bound():
    assert clamp_price(999999, base=1000) == 5000  # 5배 상한


def test_clamp_price_passthrough():
    assert clamp_price(1500, base=1000) == 1500


def test_market_price_uses_materials_and_rarity():
    weapon = {"rarity": 50, "sharpness": 50, "materials_used": [
        {"category": "일반", "qty": 2}, {"category": "특수", "qty": 1}
    ]}
    price = market_price(weapon)
    assert price > 0

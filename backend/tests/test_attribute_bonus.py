import pytest
from app.combat import attribute_bonus


# 사이클: 금 → 바람 → 흙 → 물 → 불 → 금
# weapon이 demon을 억제하면 1.3, 역이면 0.7, 그 외 1.0
@pytest.mark.parametrize("weapon,demon,expected", [
    ("금",   "바람", 1.3),
    ("바람", "흙",   1.3),
    ("흙",   "물",   1.3),
    ("물",   "불",   1.3),
    ("불",   "금",   1.3),
    ("바람", "금",   0.7),
    ("흙",   "바람", 0.7),
    ("물",   "흙",   0.7),
    ("불",   "물",   0.7),
    ("금",   "불",   0.7),
    ("금",   "금",   1.0),
    ("금",   "물",   1.0),
    ("바람", "물",   1.0),
    (None,   "불",   1.0),
    ("불",   None,   1.0),
    (None,   None,   1.0),
])
def test_attribute_bonus(weapon, demon, expected):
    assert attribute_bonus(weapon, demon) == pytest.approx(expected)

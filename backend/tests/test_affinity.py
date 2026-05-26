import pytest
from app.affinity import delta_from_ratio, allowed_max_pct, REJECT_SENTINEL


@pytest.mark.parametrize("ratio,expected", [
    (0.5, 10),
    (0.89, 10),
    (0.9, 5),
    (1.0, 5),
    (1.1, 5),
    (1.2, 5),
    (1.21, -10),
    (2.0, -10),
])
def test_delta_from_ratio(ratio, expected):
    assert delta_from_ratio(ratio) == expected


@pytest.mark.parametrize("affinity,expected", [
    (-100, REJECT_SENTINEL),
    (-50, REJECT_SENTINEL),
    (-49, 0.80),
    (-20, 0.80),
    (-19, 0.90),
    (0, 0.90),
    (19, 0.90),
    (20, 1.00),
    (49, 1.00),
    (50, 1.10),
    (100, 1.10),
])
def test_allowed_max_pct(affinity, expected):
    assert allowed_max_pct(affinity) == expected

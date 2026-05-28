from app import patience


def test_hero_start_value_호탕():
    assert patience.hero_start({"personality_tags": ["호탕"]}) == 70


def test_hero_start_value_깐깐_소심():
    assert patience.hero_start({"personality_tags": ["깐깐", "소심"]}) == 20


def test_hero_start_value_clamped_low():
    assert patience.hero_start({"personality_tags": ["깐깐", "깐깐", "깐깐"]}) == 10


def test_hero_start_value_clamped_high():
    assert patience.hero_start({"personality_tags": ["호탕", "호탕", "호탕"]}) == 90


def test_hero_start_value_unknown_tag_ignored():
    assert patience.hero_start({"personality_tags": ["호탕", "알수없음"]}) == 70


def test_merchant_start_value_range():
    results = {patience.merchant_start(player_id=1, day=d, merchant_id=1) for d in range(50)}
    assert all(30 <= v <= 70 for v in results)


def test_merchant_start_value_deterministic():
    assert patience.merchant_start(1, 5, 7) == patience.merchant_start(1, 5, 7)


def test_decrement_normal():
    assert patience.next_after_round(50, conceded=False) == 40


def test_decrement_with_concession():
    assert patience.next_after_round(50, conceded=True) == 45


def test_level_thresholds():
    assert patience.level(80) == "high"
    assert patience.level(31) == "high"
    assert patience.level(30) == "low"
    assert patience.level(1) == "low"
    assert patience.level(0) == "exhausted"
    assert patience.level(-5) == "exhausted"


def test_exhausted():
    assert patience.is_exhausted(0)
    assert patience.is_exhausted(-1)
    assert not patience.is_exhausted(1)


def test_concession_multiplier_midpoint():
    assert patience.concession_multiplier(50) == 1.0


def test_concession_multiplier_quarter_points():
    assert patience.concession_multiplier(25) == 2.0
    assert patience.concession_multiplier(75) == 2.0


def test_concession_multiplier_extremes():
    assert patience.concession_multiplier(0) == 3.0
    assert patience.concession_multiplier(100) == 3.0


def test_concession_multiplier_negative_or_over_clamps():
    assert patience.concession_multiplier(-10) == 3.0
    assert patience.concession_multiplier(150) == 3.0


def test_concession_multiplier_monotonic_from_midpoint():
    assert patience.concession_multiplier(60) < patience.concession_multiplier(70)
    assert patience.concession_multiplier(40) < patience.concession_multiplier(30)

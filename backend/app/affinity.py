"""호감도 기반 규칙 — 가격 허용 범위와 거래 후 호감도 변화."""

REJECT_SENTINEL = "reject"


def delta_from_ratio(ratio: float) -> int:
    """합의가/시세 비율 → 호감도 변화."""
    if ratio < 0.9:
        return 10
    if ratio <= 1.2:
        return 5
    return -10


def allowed_max_pct(affinity: int) -> float | str:
    """호감도 → 시세 대비 합의 가능 상한 비율 (또는 REJECT_SENTINEL)."""
    if affinity <= -50:
        return REJECT_SENTINEL
    if affinity <= -20:
        return 0.80
    if affinity <= 19:
        return 0.90
    if affinity <= 49:
        return 1.00
    return 1.10


def clamp_affinity(value: int) -> int:
    """affinity 컬럼은 -100..100 범위로 제한."""
    return max(-100, min(100, int(value)))

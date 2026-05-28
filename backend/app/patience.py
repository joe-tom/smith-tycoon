"""협상 인내심 — 시작값 계산, 라운드 감소, 임계값 판정."""
from __future__ import annotations
import random

PERSONA_DELTAS = {
    "호탕": 20, "깐깐": -20, "검소": 0, "소심": -10, "허세": -10,
}
BASE = 50
HERO_FLOOR = 10
HERO_CEIL = 90


def hero_start(hero: dict) -> int:
    delta = sum(PERSONA_DELTAS.get(tag, 0) for tag in (hero.get("personality_tags") or []))
    return max(HERO_FLOOR, min(HERO_CEIL, BASE + delta))


def merchant_start(player_id: int, day: int, merchant_id: int) -> int:
    seed = (player_id * 1_000_003 + day * 31 + merchant_id * 7 + 19) & 0xFFFFFFFF
    return random.Random(seed).randint(30, 70)


def next_after_round(current: int, conceded: bool) -> int:
    return current - (5 if conceded else 10)


def level(current: int) -> str:
    if current <= 0:
        return "exhausted"
    if current <= 30:
        return "low"
    return "high"


def is_exhausted(current: int) -> bool:
    return current <= 0


def concession_multiplier(patience: int) -> float:
    """양보폭 배수. 50에서 1.0×, 0/100 양 끝에서 3.0× (대칭 U곡선).

    인내심이 가득한 NPC는 기분이 좋아, 거의 탈진한 NPC는 빨리 끝내려고
    후하게 양보한다. 중간 구간(40~60)이 가장 빡빡하다.
    """
    distance = min(abs(patience - 50), 50)
    return 1.0 + distance / 25

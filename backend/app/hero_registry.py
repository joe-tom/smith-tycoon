from __future__ import annotations
import random
from typing import Any
from . import repo


JOBS = ["검사", "법사", "궁수", "성문 문지기", "거렁뱅이", "청소년", "군인"]
MOODS = ["여유로움", "초조함", "들떠있음", "지친 듯"]
TRAITS = ["호탕", "깐깐", "소심", "허세", "검소"]


def generate_hero(seed: int | None = None) -> dict[str, Any]:
    rng = random.Random(seed)
    return {
        "name": str(rng.randint(1, 1000)),
        "job": rng.choice(JOBS),
        "str": rng.randint(5, 15),
        "mag": rng.randint(2, 12),
        "gold": rng.randint(500, 2000),
        "mood": rng.choice(MOODS),
        "personality_tags": rng.sample(TRAITS, k=2),
        "affinity": 0,
        "status": "alive",
        "history": [],
    }


def heroes_for_today(day: int, count: int = 3) -> list[dict[str, Any]]:
    """오늘 등장할 용사 목록 — 재방문 대상 우선, 부족분 신규 생성·삽입."""
    ready = repo.list_alive_heroes_ready(day)
    ready.sort(key=lambda h: (h.get("return_day") or 0))
    picked = ready[:count]
    for _ in range(count - len(picked)):
        h = repo.insert_hero(generate_hero())
        picked.append(h)
    return picked


def schedule_return(battle_outcome: str, current_day: int) -> dict[str, Any]:
    """전투 결과별 다음 등장 일정 + 상태 필드 반환."""
    if battle_outcome == "survived":
        return {"status": "alive", "return_day": current_day + 3}
    if battle_outcome == "fled":
        return {"status": "fled", "return_day": current_day + 7}
    if battle_outcome == "died":
        return {"status": "dead", "return_day": None}
    raise ValueError(f"unknown battle outcome: {battle_outcome}")

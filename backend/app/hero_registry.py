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
    """오늘 등장할 용사 목록 — 하루의 로스터는 첫 호출에서 결정·persist 후 동일.

    구현: day_events에 kind='hero_roster' 마커를 두고 hero_ids 리스트를 저장.
    이후 호출은 마커를 읽어 같은 hero 인스턴스를 반환. 전투 결과로 return_day가
    갱신돼도 당일 슬롯 인덱스는 고정된다.
    """
    events = repo.list_day_events(day)
    roster = next((e for e in events if e["kind"] == "hero_roster"), None)
    if roster:
        ids = roster["payload"]["hero_ids"]
        return [repo.get_hero(hid) for hid in ids]

    ready = repo.list_alive_heroes_ready(day)
    ready.sort(key=lambda h: (h.get("return_day") or 0))
    picked = ready[:count]
    for _ in range(count - len(picked)):
        h = repo.insert_hero(generate_hero())
        picked.append(h)
    repo.insert_day_event(day=day, phase="forge_open", kind="hero_roster",
                          payload={"hero_ids": [h["id"] for h in picked]})
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

from __future__ import annotations
import random
from typing import Any
from . import repo


JOBS = ["검사", "법사", "궁수", "성문 문지기", "거렁뱅이", "청소년", "군인"]
MOODS = ["여유로움", "초조함", "들떠있음", "지친 듯"]
TRAITS = ["호탕", "깐깐", "소심", "허세", "검소"]

# 직업별 선호 무기. types: 잘 어울리는 무기 종류, hint: 자연어 한 줄
JOB_PREFERENCES: dict[str, dict[str, Any]] = {
    "검사":       {"types": ["한손검", "양손검"],          "hint": "검 한 자루를 원합니다"},
    "법사":       {"types": ["마법지팡이"],                "hint": "마법 지팡이를 선호합니다. 마력 친화"},
    "궁수":       {"types": ["표창", "단도"],              "hint": "원거리·경량 무기를 선호합니다"},
    "성문 문지기": {"types": ["양손둔기", "방패", "한손둔기"], "hint": "방어구·둔기 류를 좋아합니다"},
    "거렁뱅이":   {"types": ["단도", "표창"],              "hint": "값싸고 빠른 단검류를 찾습니다"},
    "청소년":     {"types": ["한손검", "단도", "표창"],     "hint": "다루기 쉬운 가벼운 무기를 원합니다"},
    "군인":       {"types": ["한손검", "양손검", "방패"],   "hint": "표준 군용 무기를 선호합니다"},
}


def preferences_for(hero: dict[str, Any]) -> dict[str, Any]:
    """직업·스탯 기반 무기 선호도."""
    pref = JOB_PREFERENCES.get(hero.get("job", ""), {"types": [], "hint": ""})
    # 스탯 기반 추가 힌트
    s, m = int(hero.get("str", 0)), int(hero.get("mag", 0))
    if m >= s + 3:
        stat_hint = "마력형 — 마법 무기·마력 요구 무기에 잘 맞음"
    elif s >= m + 3:
        stat_hint = "근력형 — 무거운 물리 무기 가능"
    else:
        stat_hint = "균형형 — 다양한 무기 사용 가능"
    return {**pref, "stat_hint": stat_hint, "str": s, "mag": m}


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
        "visit_count": 0,
    }


def heroes_for_today(player_id: int, day: int, count: int = 3) -> list[dict[str, Any]]:
    """오늘 등장할 용사 목록 — 첫 호출에서 결정·persist 후 동일.

    seed = (player_id * 1_000_003 + day * 31 + slot * 7) & 0xFFFFFFFF
    """
    events = repo.list_day_events(player_id, day)
    roster = next((e for e in events if e["kind"] == "hero_roster"), None)
    if roster:
        ids = roster["payload"]["hero_ids"]
        return [repo.get_hero(hid) for hid in ids]

    ready = repo.list_alive_heroes_ready(player_id, day)
    ready.sort(key=lambda h: (h.get("return_day") or 0))
    picked = ready[:count]
    for slot in range(count - len(picked)):
        seed = (player_id * 1_000_003 + day * 31 + slot * 7) & 0xFFFFFFFF
        h = repo.insert_hero(player_id, generate_hero(seed=seed))
        picked.append(h)
    for h in picked:
        new_count = int(h.get("visit_count", 0)) + 1
        repo.update_hero(h["id"], visit_count=new_count)
        h["visit_count"] = new_count
    repo.insert_day_event(player_id, day=day, phase="forge_open",
                          kind="hero_roster",
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

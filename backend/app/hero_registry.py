from __future__ import annotations
import random
from typing import Any
from . import repo


JOBS = [
    "검사", "성기사", "광전사",
    "법사", "흑마법사", "수도승",
    "궁수", "사냥꾼", "도적",
    "용병", "군인", "거지",
]
MOODS = ["여유로움", "초조함", "들떠있음", "지친 듯"]
TRAITS = ["호탕", "깐깐", "소심", "허세", "검소"]

# 직업별 선호 무기 (각 2종). types: 잘 어울리는 무기 종류, hint: 자연어 한 줄
JOB_PREFERENCES: dict[str, dict[str, Any]] = {
    "검사":     {"types": ["검", "둔기"],         "hint": "근접 정통파. 검과 둔기를 자유롭게 다룹니다"},
    "성기사":   {"types": ["검", "방패"],         "hint": "한 손엔 검, 다른 손엔 방패. 정의의 무게를 견딥니다"},
    "광전사":   {"types": ["둔기", "방패"],       "hint": "묵직한 둔기와 방패로 정면 돌파"},
    "법사":     {"types": ["지팡이", "투척무기"], "hint": "마력 친화. 지팡이 또는 멀리서 던지는 마법구를 선호"},
    "흑마법사": {"types": ["지팡이", "총"],       "hint": "비전과 화약, 둘 다 사도(邪道)를 안 가립니다"},
    "수도승":   {"types": ["둔기", "지팡이"],     "hint": "수련용 둔기와 단단한 지팡이를 손에 익혔습니다"},
    "궁수":     {"types": ["투척무기", "총"],     "hint": "원거리 전문. 활 대신 표창·총도 능숙합니다"},
    "사냥꾼":   {"types": ["총", "검"],           "hint": "야생에서 총과 단검을 번갈아 사용"},
    "도적":     {"types": ["투척무기", "검"],     "hint": "빠른 단검과 던지는 무기. 그림자에서 일을 끝냅니다"},
    "용병":     {"types": ["총", "둔기"],         "hint": "험한 일판 출신. 총과 둔기를 가리지 않습니다"},
    "군인":     {"types": ["검", "총"],           "hint": "제식 무기를 선호. 검과 총 모두 표준 보급"},
    "거지":     {"types": ["투척무기", "방패"],   "hint": "어디서든 주워 들고 던지거나 막습니다"},
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


def heroes_for_today(player_id: int, day: int, count: int = 3,
                     exclude_ids: set[int] | None = None) -> list[dict[str, Any]]:
    """오늘 등장할 용사 목록 — 첫 호출에서 결정·persist 후 동일.

    seed = (player_id * 1_000_003 + day * 31 + slot * 7) & 0xFFFFFFFF
    exclude_ids: 풀에서 제외할 hero_id 집합 (오늘 returning_hero로 잡힌 용사 등).
    """
    events = repo.list_day_events(player_id, day)
    roster = next((e for e in events if e["kind"] == "hero_roster"), None)
    if roster:
        ids = roster["payload"]["hero_ids"]
        return [repo.get_hero(hid) for hid in ids]

    excluded = exclude_ids or set()
    ready = [h for h in repo.list_alive_heroes_ready(player_id, day) if h["id"] not in excluded]
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

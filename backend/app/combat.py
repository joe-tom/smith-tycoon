from __future__ import annotations
import random
from typing import Any
from . import repo, state_machine
from .llm.client import complete_json

DEMONS = [
    {"type": "고블린",   "attribute": "흙",   "difficulty_range": (1, 10)},
    {"type": "지옥개",   "attribute": "불",   "difficulty_range": (3, 12)},
    {"type": "작은 영혼","attribute": "물",   "difficulty_range": (1, 8)},
    {"type": "임프",     "attribute": "불",   "difficulty_range": (5, 15)},
]


def roll_demon(seed: int | None = None) -> dict[str, Any]:
    rng = random.Random(seed)
    base = rng.choice(DEMONS)
    lo, hi = base["difficulty_range"]
    return {"type": base["type"], "attribute": base["attribute"],
            "difficulty": rng.randint(lo, hi)}


def apply_outcomes(outcomes: dict[str, str]) -> dict[str, int]:
    """결과 코드 → 평판 변화 등 델타."""
    rep = 0
    if outcomes["hero"] == "survived":
        rep += 1
    elif outcomes["hero"] == "died":
        rep -= 2
    if outcomes["weapon"] == "destroyed":
        rep -= 1
    if outcomes["demon"] == "killed":
        rep += 1
    elif outcomes["demon"] == "fled":
        rep += 0  # 소폭 ↑이지만 slice에서는 0
    return {"reputation": rep}


async def run_battle(hero_id: int, weapon_id: int | None) -> dict[str, Any]:
    hero = repo.get_hero(hero_id)
    weapon = repo.get_weapon(weapon_id) if weapon_id else None
    demon = roll_demon()
    llm = await complete_json("battle", "battle_basic",
                              hero=hero, weapon=weapon, demon=demon)
    outcomes = llm["outcomes"]
    delta = apply_outcomes(outcomes)

    player = repo.load_player()
    repo.update_player(reputation=player["reputation"] + delta["reputation"],
                       current_phase=state_machine.next_phase(player["current_phase"]))

    # hero 상태 반영
    if outcomes["hero"] == "died":
        repo.update_hero(hero_id, status="dead")

    repo.insert_battle({
        "day": player["current_day"],
        "hero_id": hero_id,
        "weapon_id": weapon_id,
        "demon": demon,
        "script_text": llm["script"],
        "outcomes": outcomes,
    })

    return {"script": llm["script"], "outcomes": outcomes,
            "next_phase": repo.load_player()["current_phase"]}

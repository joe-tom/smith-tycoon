from __future__ import annotations
import random
from typing import Any
from . import repo, state_machine, hero_registry
from .llm.client import complete_json

DEMONS = [
    {"type": "고블린",   "attribute": "흙"},
    {"type": "지옥개",   "attribute": "불"},
    {"type": "작은 영혼","attribute": "물"},
    {"type": "임프",     "attribute": "불"},
]

DIFFICULTY_BY_DAY = {1: (1, 10), 2: (3, 15), 3: (8, 22), 4: (14, 30), 5: (20, 40)}


def roll_demon(day: int = 1, seed: int | None = None) -> dict[str, Any]:
    rng = random.Random(seed)
    lo, hi = DIFFICULTY_BY_DAY.get(day, (1, 10))
    base = rng.choice(DEMONS)
    return {"type": base["type"], "attribute": base["attribute"],
            "difficulty": rng.randint(lo, hi)}


def apply_outcomes(outcomes: dict[str, str]) -> dict[str, int]:
    rep = 0
    if outcomes["hero"] == "survived":
        rep += 1
    elif outcomes["hero"] == "died":
        rep -= 2
    if outcomes["weapon"] == "destroyed":
        rep -= 1
    if outcomes["demon"] == "killed":
        rep += 1
    return {"reputation": rep}


async def run_battle(hero_id: int, weapon_id: int | None) -> dict[str, Any]:
    hero = repo.get_hero(hero_id)
    weapon = repo.get_weapon(weapon_id) if weapon_id else None
    player = repo.load_player()
    demon = roll_demon(day=player["current_day"])

    llm = await complete_json("battle", "battle_basic",
                              hero=hero, weapon=weapon, demon=demon)
    outcomes = llm["outcomes"]
    delta = apply_outcomes(outcomes)

    repo.update_player(reputation=player["reputation"] + delta["reputation"],
                       current_phase=state_machine.next_phase(player["current_phase"]))

    # 전투 결과별로 status·return_day 갱신.
    # 'injured'는 일정상 'survived'와 동일 처리 (귀환 3일 내).
    sr_outcome = outcomes["hero"] if outcomes["hero"] in ("survived", "fled", "died") else "survived"
    fields = hero_registry.schedule_return(sr_outcome, current_day=player["current_day"])
    # 무기 파괴 시 held_weapon_id 비움
    if outcomes.get("weapon") == "destroyed":
        fields["held_weapon_id"] = None
    repo.update_hero(hero_id, **fields)

    battle_row = repo.insert_battle({
        "day": player["current_day"],
        "hero_id": hero_id,
        "weapon_id": weapon_id,
        "demon": demon,
        "script_text": llm["script"],
        "outcomes": outcomes,
    })

    repo.insert_day_event(
        day=player["current_day"],
        phase=player["current_phase"],
        kind="battle",
        payload={"battle_id": battle_row["id"], "outcomes": outcomes,
                 "hero_id": hero_id, "demon": demon, "rep_delta": delta["reputation"]},
    )

    return {"script": llm["script"], "outcomes": outcomes,
            "next_phase": repo.load_player()["current_phase"]}

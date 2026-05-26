from __future__ import annotations
import random
from typing import Any
from . import repo, state_machine, hero_registry, nickname as nickname_mod, affinity as affinity_mod
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


def hero_power(hero: dict[str, Any], weapon: dict[str, Any] | None) -> float:
    """용사의 실제 전투력."""
    p = float(hero.get("str", 0) + hero.get("mag", 0))
    if weapon:
        p += weapon.get("sharpness", 0) / 2.0
        p += weapon.get("rarity", 0) / 5.0
    else:
        p *= 0.7   # 맨손 패널티
    return max(1.0, p)


def demon_threat(demon: dict[str, Any]) -> float:
    """적의 위협력. 난이도 단위를 hero power 스케일로 변환."""
    return max(1.0, float(demon["difficulty"]) * 3.0)


def decide_outcomes(hero: dict[str, Any], weapon: dict[str, Any] | None,
                    demon: dict[str, Any], seed: int | None = None) -> dict[str, str]:
    """전투 결과 코드를 결정 — power/threat 비율 + 노이즈 기반."""
    rng = random.Random(seed)
    power = hero_power(hero, weapon)
    threat = demon_threat(demon)
    ratio = (power / threat) * rng.uniform(0.75, 1.25)

    if ratio >= 2.0:
        hero_r = "survived" if rng.random() > 0.05 else "injured"
        demon_r = "killed"
    elif ratio >= 1.2:
        hero_r = rng.choices(["survived", "injured"], weights=[7, 3])[0]
        demon_r = rng.choices(["killed", "fled"], weights=[8, 2])[0]
    elif ratio >= 0.8:
        hero_r = rng.choices(["survived", "injured", "died"], weights=[3, 5, 2])[0]
        demon_r = rng.choices(["killed", "fled", "survived"], weights=[4, 4, 2])[0]
    elif ratio >= 0.5:
        hero_r = rng.choices(["injured", "died"], weights=[3, 7])[0]
        demon_r = rng.choices(["fled", "survived"], weights=[3, 7])[0]
    else:
        hero_r = "died"
        demon_r = "survived"

    if weapon is None:
        weapon_r = "none"
    elif hero_r == "died":
        weapon_r = "destroyed"
    else:
        sharp = weapon.get("sharpness", 30)
        # 예리도 낮을수록·열세일수록 파괴 확률 ↑
        destroy_p = max(0.05, 0.5 - sharp / 200) * (1.0 if ratio >= 1.0 else 1.5)
        weapon_r = "destroyed" if rng.random() < destroy_p else "preserved"

    return {"hero": hero_r, "weapon": weapon_r, "demon": demon_r}


async def run_battle(hero_id: int, weapon_id: int | None) -> dict[str, Any]:
    hero = repo.get_hero(hero_id)
    weapon = repo.get_weapon(weapon_id) if weapon_id else None
    player = repo.load_player()
    demon = roll_demon(day=player["current_day"])

    # 결과 코드는 서버가 결정. LLM은 서술만.
    outcomes = decide_outcomes(hero, weapon, demon)
    llm = await complete_json("battle", "battle_basic",
                              hero=hero, weapon=weapon, demon=demon,
                              outcomes=outcomes,
                              hero_power=int(hero_power(hero, weapon)),
                              demon_threat=int(demon_threat(demon)))
    # LLM 응답에 outcomes가 같이 와도 무시 — 서버 결정 사용
    script = llm.get("script", "전투가 끝났다.")
    delta = apply_outcomes(outcomes)

    repo.update_player(reputation=player["reputation"] + delta["reputation"],
                       current_phase=state_machine.next_phase(player["current_phase"]))

    # 전투 결과별로 status·return_day 갱신.
    # 'injured'는 일정상 'survived'와 동일 처리 (귀환 3일 내).
    sr_outcome = outcomes["hero"] if outcomes["hero"] in ("survived", "fled", "died") else "survived"
    fields = hero_registry.schedule_return(sr_outcome, current_day=player["current_day"])
    # 무기 파괴 시 held_weapon_id 비움 + affinity -5
    if outcomes.get("weapon") == "destroyed":
        fields["held_weapon_id"] = None
        current_aff = int(hero.get("affinity", 0))
        fields["affinity"] = affinity_mod.clamp_affinity(current_aff - 5)
    repo.update_hero(hero_id, **fields)

    # 별명 부여 트리거
    if outcomes.get("hero") == "survived" and outcomes.get("demon") == "killed":
        consecutive = repo.count_consecutive_survives(hero_id) + 1  # 이번 전투 포함
        refreshed_hero = repo.get_hero(hero_id)
        if nickname_mod.should_award(refreshed_hero, consecutive):
            recent_demons = [demon["type"]]
            picked = await nickname_mod.award(refreshed_hero, consecutive, recent_demons)
            if picked:
                repo.update_hero(hero_id, nickname=picked)
                repo.insert_day_event(
                    day=player["current_day"], phase=player["current_phase"],
                    kind="nickname", payload={"hero_id": hero_id, "nickname": picked},
                )

    battle_row = repo.insert_battle({
        "day": player["current_day"],
        "hero_id": hero_id,
        "weapon_id": weapon_id,
        "demon": demon,
        "script_text": script,
        "outcomes": outcomes,
    })

    repo.insert_day_event(
        day=player["current_day"],
        phase=player["current_phase"],
        kind="battle",
        payload={"battle_id": battle_row["id"], "outcomes": outcomes,
                 "hero_id": hero_id, "demon": demon, "rep_delta": delta["reputation"]},
    )

    return {"script": script, "outcomes": outcomes,
            "next_phase": repo.load_player()["current_phase"]}

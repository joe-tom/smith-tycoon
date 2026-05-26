from __future__ import annotations
import random
from typing import Any
from . import repo
from .llm.client import complete_json

CATEGORY_MULT = {"일반": 1.0, "이상한": 0.5, "특수": 1.8, "전설": 3.5}

# 노력 소비 가중치 (재료 개당)
EFFORT_COST = {"일반": 6, "이상한": 3, "특수": 10, "전설": 20}


def effort_cost(materials_used: list[dict[str, Any]]) -> int:
    """재료 카테고리 × qty 가중치 합."""
    return sum(EFFORT_COST.get(m["category"], 1) * int(m["qty"]) for m in materials_used)


def effort_penalty_pct(shortage: int) -> int:
    """부족량(양수)에 따른 예리도/희귀도 감산 퍼센트."""
    if shortage <= 0:
        return 0
    if shortage <= 10:
        return 30
    return 70


def roll_weapon_stats(categories: list[str], seed: int | None = None) -> dict[str, int]:
    """재료 카테고리 리스트 → rarity, sharpness."""
    rng = random.Random(seed)
    mult = sum(CATEGORY_MULT.get(c, 1.0) for c in categories) / max(len(categories), 1)
    base_rarity = rng.gauss(35 * mult, 15)
    base_sharp = rng.gauss(40 * mult, 15)
    return {
        "rarity": max(0, min(100, int(base_rarity))),
        "sharpness": max(0, min(100, int(base_sharp))),
    }


def _choose_attribute(materials: list[dict[str, Any]]) -> str | None:
    counts: dict[str, int] = {}
    for m in materials:
        a = m.get("attribute")
        if a:
            counts[a] = counts.get(a, 0) + 1
    if not counts:
        return None
    return max(counts, key=counts.get)


async def craft(player: dict, weapon_type: str, material_qty: dict[int, int]) -> dict[str, Any]:
    """재료를 차감하고 무기를 생성. LLM으로 이름·스킬 생성."""
    pid = player["id"]
    inv = repo.load_inventory(pid)
    inv_by_id = {row["material_id"]: row for row in inv}
    materials_used: list[dict[str, Any]] = []
    for mid, q in material_qty.items():
        row = inv_by_id.get(mid)
        if not row or row["qty"] < q:
            raise ValueError(f"insufficient material {mid}")
        materials_used.append({"id": mid, "name": row["name"], "category": row["category"],
                               "attribute": row["attribute"], "qty": q})

    stats = roll_weapon_stats([m["category"] for m in materials_used for _ in range(m["qty"])])

    # 노력 소비 + 부족 시 페널티
    player_pre = repo.load_player(pid)
    cost = effort_cost(materials_used)
    current_effort = int(player_pre.get("effort", 0))
    shortage = max(0, cost - current_effort)
    penalty = effort_penalty_pct(shortage)
    if penalty:
        stats["rarity"] = max(0, int(stats["rarity"] * (100 - penalty) / 100))
        stats["sharpness"] = max(0, int(stats["sharpness"] * (100 - penalty) / 100))
    new_effort = max(0, current_effort - cost)

    attribute = _choose_attribute(materials_used)

    name_res = await complete_json("forge_name", "forge_name_basic",
                                   weapon_type=weapon_type, materials=materials_used)
    name = name_res["name"]
    skill_res = await complete_json("forge_skill", "forge_skill_basic",
                                    weapon_name=name, weapon_type=weapon_type,
                                    rarity=stats["rarity"], sharpness=stats["sharpness"])
    skill = skill_res["skill"]

    repo.deduct_materials(pid, material_qty)
    repo.update_player(pid, effort=new_effort)
    player = repo.load_player(pid)
    weapon = repo.insert_weapon(pid, {
        "owner": "player",
        "name": name,
        "type": weapon_type,
        "rarity": stats["rarity"],
        "sharpness": stats["sharpness"],
        "attribute": attribute,
        "skill": skill,
        "str_req": max(1, stats["sharpness"] // 10),
        "mag_req": max(1, stats["rarity"] // 15),
        "enhancement_level": 0,
        "materials_used": materials_used,
        "created_day": player["current_day"],
    })
    repo.insert_day_event(
        pid,
        player["current_day"],
        player.get("current_phase", "forge_open"),
        "forge",
        {"weapon_id": weapon["id"], "name": name, "type": weapon_type,
         "rarity": stats["rarity"], "sharpness": stats["sharpness"],
         "effort_cost": cost, "effort_shortage": shortage, "penalty_pct": penalty},
    )
    return weapon

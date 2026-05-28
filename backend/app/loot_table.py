"""몹 → 전리품 드롭. 결정성 시드."""
from __future__ import annotations
import random
from typing import Any
from . import repo

BOSS_LOOT: dict[str, list[dict[str, Any]]] = {
    "surt": [{"category": "전설", "name_hint": "화염정수", "qty": 1}],
}


def _pick_from_category(category: str, rng: random.Random, n: int) -> list[dict[str, Any]]:
    pool = repo.list_materials_by_category(category)
    if not pool:
        return []
    return [{"material_id": rng.choice(pool)["id"], "qty": 1} for _ in range(n)]


def _pick_matching(category: str, name_hint: str, rng: random.Random) -> dict[str, Any] | None:
    pool = repo.list_materials_by_category(category)
    if not pool:
        return None
    matching = [m for m in pool if name_hint and name_hint in (m.get("name") or "")]
    chosen = matching[0] if matching else rng.choice(pool)
    return {"material_id": chosen["id"], "qty": 1}


def roll_loot(demon: dict[str, Any], seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    out: list[dict[str, Any]] = []
    difficulty = int(demon.get("difficulty", 1))

    if demon.get("is_boss") and demon.get("boss_id") in BOSS_LOOT:
        for tmpl in BOSS_LOOT[demon["boss_id"]]:
            picked = _pick_matching(tmpl["category"], tmpl.get("name_hint", ""), rng)
            if picked:
                picked["qty"] = tmpl["qty"]
                out.append(picked)
        out.extend(_pick_from_category("일반", rng, rng.randint(2, 3)))
        return out

    if difficulty <= 3:
        out.extend(_pick_from_category("일반", rng, rng.randint(1, 2)))
    elif difficulty <= 6:
        out.extend(_pick_from_category("일반", rng, rng.randint(2, 3)))
        if rng.random() < 0.3:
            out.extend(_pick_from_category("이상한", rng, 1))
    else:
        out.extend(_pick_from_category("일반", rng, rng.randint(2, 3)))
        if rng.random() < 0.4:
            out.extend(_pick_from_category("특수", rng, 1))

    return out

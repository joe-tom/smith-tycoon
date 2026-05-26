"""무기 강화 — 카테고리별 Δ 표 (architecture.md §11.3)."""
from __future__ import annotations
import random
from typing import Any

CATEGORY_DELTAS: dict[str, tuple[tuple[int, int], tuple[int, int]]] = {
    "일반":   ((1, 3),  (0, 2)),
    "이상한": ((0, 2),  (0, 2)),
    "특수":   ((3, 7),  (2, 5)),
    "전설":   ((7, 15), (5, 12)),
}


def roll_delta(materials: list[dict[str, Any]], seed: int | None = None) -> dict[str, int]:
    rng = random.Random(seed)
    total_sharp = 0
    total_rarity = 0
    for m in materials:
        ranges = CATEGORY_DELTAS.get(m.get("category", ""), ((0, 1), (0, 1)))
        qty = int(m.get("qty", 1))
        for _ in range(qty):
            total_sharp += rng.randint(*ranges[0])
            total_rarity += rng.randint(*ranges[1])
    return {"sharpness": total_sharp, "rarity": total_rarity}


def apply_to_weapon(weapon: dict[str, Any], delta: dict[str, int],
                    used_materials: list[dict[str, Any]]) -> dict[str, Any]:
    new = dict(weapon)
    new["sharpness"] = min(100, int(weapon.get("sharpness", 0)) + delta["sharpness"])
    new["rarity"] = min(100, int(weapon.get("rarity", 0)) + delta["rarity"])
    new["enhancement_level"] = int(weapon.get("enhancement_level", 0)) + 1
    existing = list(weapon.get("materials_used") or [])
    existing.append({
        "action": "enhance",
        "materials": used_materials,
        "delta": delta,
    })
    new["materials_used"] = existing
    return new


def bundle_estimate(weapon: dict[str, Any], materials: list[dict[str, Any]]) -> int:
    avg_sharp = 0.0
    avg_rarity = 0.0
    for m in materials:
        ranges = CATEGORY_DELTAS.get(m.get("category", ""), ((0, 1), (0, 1)))
        qty = int(m.get("qty", 1))
        avg_sharp += (ranges[0][0] + ranges[0][1]) / 2 * qty
        avg_rarity += (ranges[1][0] + ranges[1][1]) / 2 * qty
    return max(50, int(avg_sharp * 30 + avg_rarity * 60))

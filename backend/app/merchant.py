from __future__ import annotations
import json
import random
from pathlib import Path
from typing import Any

_MATERIALS_CATALOG: list[dict[str, Any]] | None = None


def _materials_catalog() -> list[dict[str, Any]]:
    global _MATERIALS_CATALOG
    if _MATERIALS_CATALOG is None:
        path = Path(__file__).parent.parent / "seed" / "materials.json"
        _MATERIALS_CATALOG = json.loads(path.read_text())
    return _MATERIALS_CATALOG


WEAPON_TYPES = ["한손검", "양손검", "한손둔기", "양손둔기", "마법지팡이", "방패", "단도", "표창", "총"]


def generate_today(day: int, seed: int | None = None) -> dict[str, Any]:
    """day별 상인 인벤토리 — materials 4~6종 + weapon 1개."""
    rng = random.Random(seed if seed is not None else f"merchant-{day}")
    catalog = _materials_catalog()

    n_materials = rng.randint(4, 6)
    chosen = rng.sample(catalog, k=min(n_materials, len(catalog)))
    materials = []
    for m in chosen:
        qty = rng.randint(1, 3)
        markup = 1.0 + rng.random() * 0.5
        materials.append({
            "material_id": m["id"], "name": m["name"], "category": m["category"],
            "attribute": m.get("attribute"), "base_price": m["base_price"],
            "qty": qty,
            "asking_price": int(m["base_price"] * qty * markup),
        })

    wt = rng.choice(WEAPON_TYPES)
    weapon = {
        "name": f"{wt} (상인 매물)",
        "type": wt,
        "rarity": 30,
        "sharpness": 30,
        "attribute": None,
        "skill": "표준품의 안정적인 효과를 가집니다.",
        "str_req": 5,
        "mag_req": 3,
        "asking_price": int(300 * (1.0 + rng.random() * 0.5)),
    }
    return {"materials": materials, "weapon": weapon}


def bundle_market_price(bundle: dict[str, Any]) -> int:
    total = sum(m["base_price"] * m.get("qty", 1) for m in bundle["materials"])
    if bundle.get("weapon"):
        total += bundle["weapon"]["asking_price"]
    return max(10, total)
